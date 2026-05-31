import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import IntegrityError, transaction
from django.db.transaction import on_commit
from django.db.models import QuerySet

from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from core.clients.notification_client import notification_client
from apps.membership.exceptions import (
    CannotRemoveOwnerException,
    MembershipAlreadyExistsException,
    MembershipForbiddenException,
    MembershipNotFoundException,
    RoleUpdateForbiddenException,
)
from apps.membership.models.chat_membership import ChatMembership
from apps.membership.repositories.membership_repository import membership_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import ADD_MEMBER, LEAVE_CHAT, LIST_MEMBERS, LIST_MY_MEMBERSHIPS, MANAGE_MEMBERS, \
    REMOVE_MEMBER, UPDATE_MEMBER, UPDATE_MEMBER_ROLE
from core.exceptions import ValidationException

logger = logging.getLogger(__name__)

_VALID_TRANSITIONS: dict[str, set[str]] = {
    ChatMembership.Status.PENDING: {ChatMembership.Status.ACTIVE, ChatMembership.Status.INACTIVE},
    ChatMembership.Status.ACTIVE: {ChatMembership.Status.INACTIVE},
    ChatMembership.Status.INACTIVE: {ChatMembership.Status.ACTIVE},
}


def _broadcast_member_joined(chat_id: int, member_id: int) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"chat_{chat_id}",
            {"type": "member_joined", "member_id": member_id},
        )
    except Exception:
        logger.warning(
            "Failed to broadcast member_joined for chat %d member %d",
            chat_id,
            member_id,
            exc_info=True,
        )


def _broadcast_member_left(chat_id: int, member_id: int) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"chat_{chat_id}",
            {"type": "member_left", "member_id": member_id},
        )
    except Exception:
        logger.warning(
            "Failed to broadcast member_left for chat %d member %d",
            chat_id,
            member_id,
            exc_info=True,
        )


class MembershipService:
    def list_members(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            status: str | None = "active",
    ) -> QuerySet[ChatMembership]:
        AccessControl.require_permissions(user, frozenset({LIST_MEMBERS}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        self._require_active_member(chat_id, user.id)
        return membership_repository.list_by_chat(chat_id, status=status)

    def list_members_admin(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            status: str | None = None,
    ) -> QuerySet[ChatMembership]:
        AccessControl.require_permissions(user, frozenset({MANAGE_MEMBERS}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        return membership_repository.list_by_chat(chat_id, status=status)

    def list_my_memberships(
            self,
            user: AuthenticatedUser,
            status: str | None = None,
    ) -> QuerySet[ChatMembership]:
        AccessControl.require_permissions(user, frozenset({LIST_MY_MEMBERSHIPS}))
        return membership_repository.list_by_member(member_id=user.id, status=status)

    @transaction.atomic
    def add_members(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            member_ids: list[int],
    ) -> list[ChatMembership]:
        AccessControl.require_permissions(user, frozenset({ADD_MEMBER}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        is_creator = chat.created_by == user.id
        is_owner_member = membership_repository.is_chat_owner(chat_id, user.id)
        if not is_creator and not is_owner_member:
            raise MembershipForbiddenException("Only an owner or the chat creator can add members")

        existing = membership_repository.get_existing_member_ids_in(chat_id, member_ids)
        if existing:
            first = next(iter(existing))
            raise MembershipAlreadyExistsException(
                f"User {first} is already a member of chat {chat_id}"
            )

        created = []
        for member_id in member_ids:
            try:
                membership = membership_repository.create(
                    member_id=member_id,
                    chat_id=chat_id,
                    status="pending",
                    created_by=user.id,
                )
                created.append(membership)
            except IntegrityError:
                raise MembershipAlreadyExistsException(
                    f"User {member_id} is already a member of chat {chat_id}"
                )

        logger.info(
            "Members added to chat.",
            extra={
                "chat_id": chat_id,
                "added_by": user.id,
                "member_ids": member_ids,
            },
        )

        if created:
            receiver_ids = [m.member_id for m in created]
            actor_id = user.id
            actor_name = user.username or user.email
            context = {"chat_id": chat_id, "chat_name": chat.name}
            idem_key = f"chat-{chat_id}-invite-{'-'.join(str(i) for i in sorted(receiver_ids))}"
            on_commit(lambda: notification_client.emit_event(
                event_type="chat.member.invited",
                recipient_ids=receiver_ids,
                actor_id=actor_id,
                actor_name=actor_name,
                context=context,
                idempotency_key=idem_key,
            ))

        return created

    @transaction.atomic
    def update_member(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            member_id: int,
            new_status: str,
    ) -> ChatMembership:
        AccessControl.require_permissions(user, frozenset({UPDATE_MEMBER}))

        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if user.id != member_id:
            raise MembershipForbiddenException(
                "Only the invited member can update their own status"
            )

        if member_id == chat.created_by:
            raise CannotRemoveOwnerException("The chat owner's membership status cannot be changed")

        membership = membership_repository.get_by_chat_and_member_for_update(chat_id, member_id)
        if membership is None:
            raise MembershipNotFoundException()

        allowed = _VALID_TRANSITIONS.get(membership.status, set())
        if new_status not in allowed:
            raise ValidationException(
                detail=f"Cannot transition membership from '{membership.status}' to '{new_status}'.",
                error_code="invalid_status_transition",
            )

        membership = membership_repository.update_status(
            membership, new_status=new_status, updated_by=user.id
        )

        if new_status == ChatMembership.Status.ACTIVE:
            on_commit(lambda: _broadcast_member_joined(chat_id, member_id))
        elif new_status == ChatMembership.Status.INACTIVE:
            on_commit(lambda: _broadcast_member_left(chat_id, member_id))

        logger.info(
            "Membership updated.",
            extra={
                "chat_id": chat_id,
                "member_id": member_id,
                "new_status": new_status,
                "updated_by": user.id,
            },
        )
        return membership

    @transaction.atomic
    def remove_member(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            member_id: int,
    ) -> None:
        AccessControl.require_permissions(user, frozenset({REMOVE_MEMBER}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if chat.created_by == member_id:
            raise CannotRemoveOwnerException()

        if not membership_repository.is_chat_owner(chat_id, user.id):
            raise MembershipForbiddenException(
                "Only an owner can remove members"
            )

        membership = membership_repository.get_by_chat_and_member_for_update(chat_id, member_id)
        if membership is None:
            raise MembershipNotFoundException()

        membership_repository.soft_delete(membership, deleted_by=user.id)
        on_commit(lambda: _broadcast_member_left(chat_id, member_id))
        actor_id = user.id
        actor_name = user.username or user.email
        on_commit(lambda m=member_id: notification_client.emit_event(
            event_type="chat.member.removed",
            recipient_ids=[m],
            actor_id=actor_id,
            actor_name=actor_name,
            context={"chat_id": chat_id},
        ))
        logger.info(
            "Member removed from chat.",
            extra={
                "chat_id": chat_id,
                "member_id": member_id,
                "removed_by": user.id,
            },
        )

    @transaction.atomic
    def leave_chat(self, user: AuthenticatedUser, chat_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({LEAVE_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if chat.created_by == user.id:
            raise CannotRemoveOwnerException(
                "The owner cannot leave the chat. Delete it instead."
            )

        membership = membership_repository.get_by_chat_and_member_for_update(chat_id, user.id)
        if membership is None:
            raise MembershipNotFoundException()

        membership_repository.soft_delete(membership, deleted_by=user.id)
        on_commit(lambda: _broadcast_member_left(chat_id, user.id))
        logger.info(
            "User left chat.",
            extra={"chat_id": chat_id, "user_id": user.id},
        )

    @transaction.atomic
    def update_member_role(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            member_id: int,
            role: str,
    ) -> ChatMembership:
        AccessControl.require_permissions(user, frozenset({UPDATE_MEMBER_ROLE}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        is_creator = chat.created_by == user.id
        is_owner_member = membership_repository.is_chat_owner(chat_id, user.id)
        if not is_creator and not is_owner_member:
            raise RoleUpdateForbiddenException()
        if member_id == chat.created_by:
            raise RoleUpdateForbiddenException()
        membership = membership_repository.update_role(chat_id, member_id, role, updated_by=user.id)
        if membership is None:
            raise MembershipNotFoundException()
        logger.info(
            "Member role updated.",
            extra={"chat_id": chat_id, "member_id": member_id, "role": role, "updated_by": user.id},
        )
        return membership

    @staticmethod
    def _require_active_member(chat_id: int, user_id: int) -> None:
        if not membership_repository.is_active_member(chat_id, user_id):
            raise MembershipForbiddenException(
                "You must be an active member of this chat"
            )


membership_service = MembershipService()
