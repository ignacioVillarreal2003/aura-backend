import logging
from django.db import IntegrityError, transaction
from django.db.transaction import on_commit
from django.db.models import QuerySet

from apps.chat.exceptions import ChatNotFoundException
from apps.chat.models.chat import Chat
from apps.chat.repositories.chat_repository import chat_repository
from core.clients.notification_client import notification_client
from apps.membership.dtos import ROLE_EDITOR, ROLE_OWNER, ROLE_READER, ChatMembershipCheck
from apps.membership.exceptions import (
    CannotRemoveOwnerException,
    MembershipAlreadyExistsException,
    MembershipForbiddenException,
    MembershipNotFoundException,
    RoleUpdateForbiddenException,
)
from apps.membership.models.chat_membership import ChatMembership
from apps.membership.repositories.membership_repository import membership_repository
from core.ws.group_broadcast import send_to_chat_group
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import ADD_MEMBER, LEAVE_CHAT, LIST_MEMBERS, LIST_MY_MEMBERSHIPS, MANAGE_MEMBERS, \
    REMOVE_MEMBER, UPDATE_MEMBER, UPDATE_MEMBER_ROLE
from core.exceptions import ValidationException

logger = logging.getLogger(__name__)

_VALID_TRANSITIONS: dict[str, set[str]] = {
    ChatMembership.Status.PENDING: {ChatMembership.Status.ACTIVE},
}


def _broadcast_member_joined(chat_id: int, member_id: int) -> None:
    send_to_chat_group(chat_id, {"type": "member_joined", "member_id": member_id})


def _broadcast_member_left(chat_id: int, member_id: int) -> None:
    send_to_chat_group(chat_id, {"type": "member_left", "member_id": member_id})


def _broadcast_membership_revoked(chat_id: int, member_id: int) -> None:
    """Tell the chat group that ``member_id`` lost access so their own open
    sockets can close instead of lingering subscribed to the group."""
    send_to_chat_group(chat_id, {"type": "membership_revoked", "member_id": member_id})


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

    def check_membership(
            self,
            caller: AuthenticatedUser,
            chat_id: int,
            user_id: int,
    ) -> ChatMembershipCheck:
        """Internal: report whether ``user_id`` belongs to ``chat_id`` and with
        which role, so another service can authorize access to that chat's documents.

        Read-only and idempotent. The role is resolved with a single indexed lookup
        on ``(chat_id, member_id, status)``; the chat row is fetched by primary key
        only to distinguish a missing/deleted chat (404) from a genuine non-member
        (200, ``is_member=False``).
        """
        self._authorize_membership_check(caller, user_id)

        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        role = self._resolve_external_role(chat, user_id)
        return ChatMembershipCheck(
            chat_id=chat_id,
            user_id=user_id,
            is_member=role is not None,
            role=role,
        )

    @staticmethod
    def _authorize_membership_check(caller: AuthenticatedUser, user_id: int) -> None:
        # Any user may always check their own membership.
        if caller.id == user_id:
            return
        # Inspecting another user's membership is an administrative action.
        AccessControl.require_permissions(caller, frozenset({MANAGE_MEMBERS}))

    @staticmethod
    def _resolve_external_role(chat: Chat, user_id: int) -> str | None:
        # The chat creator is an implicit owner, even without a membership row.
        if chat.created_by == user_id:
            return ROLE_OWNER
        role = membership_repository.get_role(chat.id, user_id)
        if role is None:
            return None
        # Expose the granular role so callers can tell read-only readers apart
        # from writers, not just ownership.
        if role == ChatMembership.Role.OWNER:
            return ROLE_OWNER
        if role == ChatMembership.Role.READER:
            return ROLE_READER
        return ROLE_EDITOR

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
                with transaction.atomic():
                    membership = membership_repository.create(
                        member_id=member_id,
                        chat_id=chat_id,
                        status="pending",
                        created_by=user.id,
                    )
            except IntegrityError:
                raise MembershipAlreadyExistsException(
                    f"User {member_id} is already a member of chat {chat_id}"
                )
            created.append(membership)

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
            on_commit(lambda: notification_client.emit_event(
                event_type="chat.member.invited",
                recipient_ids=receiver_ids,
                actor_id=actor_id,
                actor_name=actor_name,
                context=context,
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
        on_commit(lambda: _broadcast_membership_revoked(chat_id, member_id))
        actor_id = user.id
        actor_name = user.username or user.email
        on_commit(lambda m=member_id: notification_client.emit_event(
            event_type="chat.member.removed",
            recipient_ids=[m],
            actor_id=actor_id,
            actor_name=actor_name,
            context={"chat_id": chat_id, "chat_name": chat.name},
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
        on_commit(lambda: _broadcast_membership_revoked(chat_id, user.id))
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
