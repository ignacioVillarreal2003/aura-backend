import logging
from django.db import transaction
from django.db.models import QuerySet

from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.models.chat import Chat
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import CREATE_CHAT, GET_CHAT, LIST_CHATS, UPDATE_CHAT, DELETE_CHAT

logger = logging.getLogger(__name__)


class ChatService:
    @transaction.atomic
    def create_chat(self, user: AuthenticatedUser, name: str, **kwargs) -> Chat:
        AccessControl.require_permissions(user, frozenset({CREATE_CHAT}))
        chat = chat_repository.create(name=name, created_by=user.id)

        membership_repository.create(
            member_id=user.id,
            chat_id=chat.id,
            status="active",
            created_by=user.id,
        )

        logger.info(
            "Chat created.",
            extra={"chat_id": chat.id, "user_id": user.id},
        )
        return chat

    def get_chat(self, user: AuthenticatedUser, chat_id: int) -> Chat:
        AccessControl.require_permissions(user, frozenset({GET_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if not membership_repository.is_active_member(chat_id=chat_id, member_id=user.id):
            raise ChatAccessDeniedException()

        return chat

    def list_chats(self, user: AuthenticatedUser) -> QuerySet[Chat]:
        AccessControl.require_permissions(user, frozenset({LIST_CHATS}))
        return chat_repository.get_chats_for_member(member_id=user.id)

    def list_own_chats(self, user: AuthenticatedUser) -> QuerySet[Chat]:
        AccessControl.require_permissions(user, frozenset({LIST_CHATS}))
        return chat_repository.get_chats_created_by(user_id=user.id)

    def update_chat(self, user: AuthenticatedUser, chat_id: int, **fields) -> Chat:
        AccessControl.require_permissions(user, frozenset({UPDATE_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can update the chat")

        chat = chat_repository.update(chat, updated_by=user.id, **fields)
        logger.info(
            "Chat updated.",
            extra={"chat_id": chat.id, "user_id": user.id},
        )
        return chat

    def delete_chat(self, user: AuthenticatedUser, chat_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({DELETE_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can delete the chat")

        chat_repository.soft_delete(chat, deleted_by=user.id)
        logger.info(
            "Chat deleted.",
            extra={"chat_id": chat_id, "user_id": user.id},
        )

    def archive_chat(self, user: AuthenticatedUser, chat_id: int) -> Chat:
        AccessControl.require_permissions(user, frozenset({UPDATE_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can archive the chat")

        chat = chat_repository.set_archived(chat, archived=True, updated_by=user.id)
        logger.info(
            "Chat archived.",
            extra={"chat_id": chat_id, "user_id": user.id},
        )
        return chat

    def unarchive_chat(self, user: AuthenticatedUser, chat_id: int) -> Chat:
        AccessControl.require_permissions(user, frozenset({UPDATE_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can unarchive the chat")

        chat = chat_repository.set_archived(chat, archived=False, updated_by=user.id)
        logger.info(
            "Chat unarchived.",
            extra={"chat_id": chat_id, "user_id": user.id},
        )
        return chat


chat_service = ChatService()
