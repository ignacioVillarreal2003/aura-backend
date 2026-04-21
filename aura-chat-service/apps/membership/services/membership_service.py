import logging

from django.db import IntegrityError
from django.db.models import QuerySet

from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.exceptions import (
    CannotRemoveOwnerException,
    MembershipAlreadyExistsException,
    MembershipForbiddenException,
    MembershipNotFoundException,
)
from apps.membership.models.chat_membership import ChatMembership
from apps.membership.repositories.membership_repository import membership_repository
from core.authentication.authenticated_user import AuthenticatedUser

logger = logging.getLogger(__name__)


class MembershipService:
    def list_members(self, user: AuthenticatedUser, chat_id: int) -> QuerySet[ChatMembership]:
        self._require_active_member(chat_id, user.id)
        return membership_repository.list_by_chat(chat_id)

    def add_members(
        self,
        user: AuthenticatedUser,
        chat_id: int,
        member_ids: list[int],
    ) -> list[ChatMembership]:
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        self._require_active_member(chat_id, user.id)

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
        return created

    def update_member(
        self,
        user: AuthenticatedUser,
        chat_id: int,
        member_id: int,
        new_status: str,
    ) -> ChatMembership:
        self._require_active_member(chat_id, user.id)

        membership = membership_repository.get_by_chat_and_member(chat_id, member_id)
        if membership is None:
            raise MembershipNotFoundException()

        membership = membership_repository.update_status(
            membership, new_status=new_status, updated_by=user.id
        )
        logger.info(
            "Membership updated.",
            extra={
                "chat_id": chat_id,
                "member_id": member_id,
                "new_status": new_status,
            },
        )
        return membership

    def remove_member(
        self,
        user: AuthenticatedUser,
        chat_id: int,
        member_id: int,
    ) -> None:
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if chat.created_by == member_id:
            raise CannotRemoveOwnerException()

        is_self = user.id == member_id
        is_owner = chat.created_by == user.id

        if not is_self and not is_owner:
            raise MembershipForbiddenException(
                "Only the chat owner or the member themselves can remove a member"
            )

        membership = membership_repository.get_by_chat_and_member(chat_id, member_id)
        if membership is None:
            raise MembershipNotFoundException()

        membership_repository.soft_delete(membership, deleted_by=user.id)
        logger.info(
            "Member removed from chat.",
            extra={
                "chat_id": chat_id,
                "member_id": member_id,
                "removed_by": user.id,
            },
        )

    def leave_chat(self, user: AuthenticatedUser, chat_id: int) -> None:
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if chat.created_by == user.id:
            raise CannotRemoveOwnerException(
                "The owner cannot leave the chat. Delete it instead."
            )

        membership = membership_repository.get_by_chat_and_member(chat_id, user.id)
        if membership is None:
            raise MembershipNotFoundException()

        membership_repository.soft_delete(membership, deleted_by=user.id)
        logger.info(
            "User left chat.",
            extra={"chat_id": chat_id, "user_id": user.id},
        )

    @staticmethod
    def _require_active_member(chat_id: int, user_id: int) -> None:
        if not membership_repository.is_active_member(chat_id, user_id):
            raise MembershipForbiddenException(
                "You must be an active member of this chat"
            )


membership_service = MembershipService()
