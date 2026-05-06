import logging
from django.db import transaction
from django.db.models import QuerySet

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.models.chat import Chat
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.repositories.message_repository import message_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import CREATE_CHAT, DELETE_CHAT, GET_CHAT, LIST_CHATS, UPDATE_CHAT


def _broadcast_chat_locked_changed(chat_id: int, is_locked: bool, by: int) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"chat_{chat_id}",
        {"type": "chat_locked_changed", "is_locked": is_locked, "by": by},
    )

logger = logging.getLogger(__name__)


class ChatService:
    @transaction.atomic
    def create_chat(self, user: AuthenticatedUser, name: str, **kwargs) -> Chat:
        AccessControl.require_permissions(user, frozenset({CREATE_CHAT}))
        chat = chat_repository.create(name=name, created_by=user.id, **kwargs)

        membership_repository.create(
            member_id=user.id,
            chat_id=chat.id,
            status="active",
            role="owner",
            created_by=user.id,
        )

        logger.info("Chat created.", extra={"chat_id": chat.id, "user_id": user.id})
        return chat

    def get_chat(self, user: AuthenticatedUser, chat_id: int) -> Chat:
        AccessControl.require_permissions(user, frozenset({GET_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if not membership_repository.is_active_member(chat_id=chat_id, member_id=user.id):
            raise ChatAccessDeniedException()

        return chat

    def list_chats(
        self,
        user: AuthenticatedUser,
        search: str | None = None,
        ordering: str | None = None,
        tags: list[str] | None = None,
    ) -> QuerySet[Chat]:
        AccessControl.require_permissions(user, frozenset({LIST_CHATS}))
        return chat_repository.get_chats_for_member(
            member_id=user.id,
            search=search,
            ordering=ordering or "-last_message_at",
            tags=tags,
        )

    def list_own_chats(
        self,
        user: AuthenticatedUser,
        search: str | None = None,
        ordering: str | None = None,
        tags: list[str] | None = None,
    ) -> QuerySet[Chat]:
        AccessControl.require_permissions(user, frozenset({LIST_CHATS}))
        return chat_repository.get_chats_created_by(
            user_id=user.id,
            search=search,
            ordering=ordering or "-created_at",
            tags=tags,
        )

    @transaction.atomic
    def update_chat(self, user: AuthenticatedUser, chat_id: int, **fields) -> Chat:
        AccessControl.require_permissions(user, frozenset({UPDATE_CHAT}))
        chat = chat_repository.get_by_id_for_update(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can update the chat")

        chat = chat_repository.update(chat, updated_by=user.id, **fields)
        logger.info("Chat updated.", extra={"chat_id": chat.id, "user_id": user.id})
        return chat

    @transaction.atomic
    def delete_chat(self, user: AuthenticatedUser, chat_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({DELETE_CHAT}))
        chat = chat_repository.get_by_id_for_update(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can delete the chat")

        membership_repository.soft_delete_by_chat(chat_id, deleted_by=user.id)
        message_repository.soft_delete_by_chat(chat_id, deleted_by=user.id)
        chat_repository.soft_delete(chat, deleted_by=user.id)
        logger.info("Chat deleted.", extra={"chat_id": chat_id, "user_id": user.id})

    def list_archived_chats(
        self,
        user: AuthenticatedUser,
        search: str | None = None,
        ordering: str | None = None,
        tags: list[str] | None = None,
    ) -> QuerySet[Chat]:
        AccessControl.require_permissions(user, frozenset({LIST_CHATS}))
        return chat_repository.get_archived_chats_for_member(
            member_id=user.id,
            search=search,
            ordering=ordering or "-last_message_at",
            tags=tags,
        )

    def archive_chats(self, user: AuthenticatedUser, chat_ids: list[int]) -> int:
        AccessControl.require_permissions(user, frozenset({LIST_CHATS}))
        count = membership_repository.archive_chats(chat_ids=chat_ids, member_id=user.id)
        logger.info("Chats archived.", extra={"chat_ids": chat_ids, "user_id": user.id, "count": count})
        return count

    def unarchive_chats(self, user: AuthenticatedUser, chat_ids: list[int]) -> int:
        AccessControl.require_permissions(user, frozenset({LIST_CHATS}))
        count = membership_repository.unarchive_chats(chat_ids=chat_ids, member_id=user.id)
        logger.info("Chats unarchived.", extra={"chat_ids": chat_ids, "user_id": user.id, "count": count})
        return count

    def pin_chat(self, user: AuthenticatedUser, chat_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({GET_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id=chat_id, member_id=user.id):
            raise ChatAccessDeniedException()
        membership_repository.pin(chat_id=chat_id, member_id=user.id)
        logger.info("Chat pinned.", extra={"chat_id": chat_id, "user_id": user.id})

    def unpin_chat(self, user: AuthenticatedUser, chat_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({GET_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id=chat_id, member_id=user.id):
            raise ChatAccessDeniedException()
        membership_repository.unpin(chat_id=chat_id, member_id=user.id)
        logger.info("Chat unpinned.", extra={"chat_id": chat_id, "user_id": user.id})

    def lock_chat(self, user: AuthenticatedUser, chat_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({UPDATE_CHAT}))
        chat = chat_repository.get_by_id_for_update(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can lock the chat")
        chat_repository.update(chat, updated_by=user.id, is_locked=True)
        _broadcast_chat_locked_changed(chat_id, is_locked=True, by=user.id)
        from apps.chat.services.webhook_service import webhook_service
        webhook_service.fire_event(chat_id, "chat.locked", {"locked_by": user.id})
        logger.info("Chat locked.", extra={"chat_id": chat_id, "user_id": user.id})

    def unlock_chat(self, user: AuthenticatedUser, chat_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({UPDATE_CHAT}))
        chat = chat_repository.get_by_id_for_update(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can unlock the chat")
        chat_repository.update(chat, updated_by=user.id, is_locked=False)
        _broadcast_chat_locked_changed(chat_id, is_locked=False, by=user.id)
        from apps.chat.services.webhook_service import webhook_service
        webhook_service.fire_event(chat_id, "chat.unlocked", {"unlocked_by": user.id})
        logger.info("Chat unlocked.", extra={"chat_id": chat_id, "user_id": user.id})

    def mute_chat(self, user: AuthenticatedUser, chat_id: int, muted_until) -> None:
        AccessControl.require_permissions(user, frozenset({GET_CHAT}))
        if not membership_repository.is_active_member(chat_id=chat_id, member_id=user.id):
            raise ChatAccessDeniedException()
        membership_repository.mute(chat_id=chat_id, member_id=user.id, muted_until=muted_until)
        logger.info("Chat muted.", extra={"chat_id": chat_id, "user_id": user.id})

    def unmute_chat(self, user: AuthenticatedUser, chat_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({GET_CHAT}))
        if not membership_repository.is_active_member(chat_id=chat_id, member_id=user.id):
            raise ChatAccessDeniedException()
        membership_repository.unmute(chat_id=chat_id, member_id=user.id)
        logger.info("Chat unmuted.", extra={"chat_id": chat_id, "user_id": user.id})


chat_service = ChatService()
