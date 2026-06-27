import logging
from django.db import transaction
from django.db.models import QuerySet

from apps.chat.ai_reply_lock import release as _release_ai_lock
from apps.chat.ai_reply_lock import try_acquire as _try_acquire_ai_lock
from apps.chat.exceptions import (
    ChatAccessDeniedException,
    ChatAiReplyInProgressException,
    ChatNotFoundException,
)
from apps.chat.models.chat import Chat
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.membership.models.chat_membership import ChatMembership
from core.ws.group_broadcast import send_to_chat_group
from core.clients.document_processing_client import document_processing_client
from core.clients.notification_client import notification_client
from apps.chat.repositories.share_link_repository import share_link_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import (
    ARCHIVE_CHAT,
    CLEAR_CHAT_HISTORY,
    CREATE_CHAT,
    DELETE_CHAT,
    GET_CHAT,
    LIST_ARCHIVED_CHATS,
    LIST_CHATS,
    LIST_MY_CHATS,
    LOCK_CHAT,
    MANAGE_CHATS,
    MARK_CHAT_AS_READ,
    PIN_CHAT,
    UNARCHIVE_CHAT,
    UPDATE_CHAT,
)

logger = logging.getLogger(__name__)


def _broadcast_chat_locked_changed(chat_id: int, is_locked: bool, by: int) -> None:
    send_to_chat_group(
        chat_id,
        {"type": "chat_locked_changed", "is_locked": is_locked, "by": by},
    )


def _broadcast_chat_content_cleared(chat_id: int, by: int) -> None:
    send_to_chat_group(chat_id, {"type": "chat_content_cleared", "by": by})


def _broadcast_chat_deleted(chat_id: int, by: int) -> None:
    send_to_chat_group(chat_id, {"type": "chat_deleted", "by": by})


class ChatService:
    @staticmethod
    def _require_owner_or_creator(chat: Chat, user: AuthenticatedUser, action: str) -> None:
        if chat.created_by == user.id:
            return
        if membership_repository.is_chat_owner(chat_id=chat.id, member_id=user.id):
            return
        raise ChatAccessDeniedException(f"Only the chat owner can {action} the chat")

    @transaction.atomic
    def create_chat(self, user: AuthenticatedUser, name: str, **kwargs) -> Chat:
        AccessControl.require_permissions(user, frozenset({CREATE_CHAT}))
        chat = chat_repository.create(name=name, created_by=user.id, **kwargs)

        membership_repository.create(
            member_id=user.id,
            chat_id=chat.id,
            status=ChatMembership.Status.ACTIVE,
            role=ChatMembership.Role.OWNER,
            created_by=user.id,
        )

        logger.info("Chat created.", extra={"chat_id": chat.id, "user_id": user.id})
        return chat

    def get_chat(self, user: AuthenticatedUser, chat_id: int) -> Chat:
        AccessControl.require_permissions(user, frozenset({GET_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        membership = membership_repository.get_by_chat_and_member(chat_id=chat_id, member_id=user.id)
        if membership is None or membership.status != "active":
            raise ChatAccessDeniedException()

        setattr(chat, "pinned_at", membership.pinned_at)
        setattr(chat, "archived_at", membership.archived_at)

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
        AccessControl.require_permissions(user, frozenset({LIST_MY_CHATS}))
        return chat_repository.get_chats_created_by(
            user_id=user.id,
            search=search,
            ordering=ordering or "-created_at",
            tags=tags,
        )

    def list_all_chats(
            self,
            user: AuthenticatedUser,
            search: str | None = None,
            ordering: str | None = None,
            tags: list[str] | None = None,
    ) -> QuerySet[Chat]:
        AccessControl.require_permissions(user, frozenset({MANAGE_CHATS}))
        return chat_repository.list_all(
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

        self._require_owner_or_creator(chat, user, "update")

        chat = chat_repository.update(chat, updated_by=user.id, **fields)
        logger.info("Chat updated.", extra={"chat_id": chat.id, "user_id": user.id})
        return chat

    @transaction.atomic
    def delete_chat(self, user: AuthenticatedUser, chat_id: int) -> None:
        from apps.artifact.services.artifact_service import clear_chat_artifacts

        AccessControl.require_permissions(user, frozenset({DELETE_CHAT}))
        chat = chat_repository.get_by_id_for_update(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        self._require_owner_or_creator(chat, user, "delete")

        share_link_repository.deactivate_by_chat(chat_id)
        membership_repository.soft_delete_by_chat(chat_id, deleted_by=user.id)
        clear_chat_artifacts(chat_id, deleted_by=user.id)
        chat_repository.soft_delete(chat, deleted_by=user.id)
        # The documents uploaded to this chat live in the document-processing
        # service; ask it to soft-delete them once our own deletion commits.
        transaction.on_commit(
            lambda: document_processing_client.delete_documents_by_chat(chat_id, user)
        )
        transaction.on_commit(lambda: _release_ai_lock(chat_id))
        # Tell every connected member the chat is gone so their sockets can close
        # instead of lingering subscribed to a dead group.
        transaction.on_commit(lambda: _broadcast_chat_deleted(chat_id, user.id))
        logger.info("Chat deleted.", extra={"chat_id": chat_id, "user_id": user.id})

    def list_archived_chats(
            self,
            user: AuthenticatedUser,
            search: str | None = None,
            ordering: str | None = None,
            tags: list[str] | None = None,
    ) -> QuerySet[Chat]:
        AccessControl.require_permissions(user, frozenset({LIST_ARCHIVED_CHATS}))
        return chat_repository.get_archived_chats_for_member(
            member_id=user.id,
            search=search,
            ordering=ordering or "-last_message_at",
            tags=tags,
        )

    def archive_chats(self, user: AuthenticatedUser, chat_ids: list[int]) -> int:
        AccessControl.require_permissions(user, frozenset({ARCHIVE_CHAT}))
        accessible = membership_repository.get_active_chat_ids_for_member(user.id, chat_ids)
        invalid = set(chat_ids) - accessible
        if invalid:
            raise ChatAccessDeniedException()
        count = membership_repository.archive_chats(chat_ids=chat_ids, member_id=user.id)
        logger.info("Chats archived.", extra={"chat_ids": chat_ids, "user_id": user.id, "count": count})
        return count

    def unarchive_chats(self, user: AuthenticatedUser, chat_ids: list[int]) -> int:
        AccessControl.require_permissions(user, frozenset({UNARCHIVE_CHAT}))
        accessible = membership_repository.get_active_chat_ids_for_member(user.id, chat_ids)
        invalid = set(chat_ids) - accessible
        if invalid:
            raise ChatAccessDeniedException()
        count = membership_repository.unarchive_chats(chat_ids=chat_ids, member_id=user.id)
        logger.info("Chats unarchived.", extra={"chat_ids": chat_ids, "user_id": user.id, "count": count})
        return count

    def delete_chats(self, user: AuthenticatedUser, chat_ids: list[int]) -> int:
        AccessControl.require_permissions(user, frozenset({DELETE_CHAT}))
        deleted = 0
        for chat_id in chat_ids:
            try:
                self.delete_chat(user=user, chat_id=chat_id)
                deleted += 1
            except (ChatNotFoundException, ChatAccessDeniedException):
                continue
        logger.info("Chats deleted (bulk).", extra={"user_id": user.id, "count": deleted})
        return deleted

    def pin_chat(self, user: AuthenticatedUser, chat_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({PIN_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id=chat_id, member_id=user.id):
            raise ChatAccessDeniedException()
        membership_repository.pin(chat_id=chat_id, member_id=user.id)
        logger.info("Chat pinned.", extra={"chat_id": chat_id, "user_id": user.id})

    def unpin_chat(self, user: AuthenticatedUser, chat_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({PIN_CHAT}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id=chat_id, member_id=user.id):
            raise ChatAccessDeniedException()
        membership_repository.unpin(chat_id=chat_id, member_id=user.id)
        logger.info("Chat unpinned.", extra={"chat_id": chat_id, "user_id": user.id})

    def lock_chat(self, user: AuthenticatedUser, chat_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({LOCK_CHAT}))
        with transaction.atomic():
            chat = chat_repository.get_by_id_for_update(chat_id)
            if chat is None:
                raise ChatNotFoundException()
            self._require_owner_or_creator(chat, user, "lock")
            chat_repository.update(chat, updated_by=user.id, is_locked=True)
        _broadcast_chat_locked_changed(chat_id, is_locked=True, by=user.id)
        recipient_ids = [
            member_id
            for member_id in membership_repository.get_active_member_ids(chat_id)
            if member_id != user.id
        ]
        if recipient_ids:
            notification_client.emit_event(
                event_type="chat.locked",
                recipient_ids=recipient_ids,
                actor_id=user.id,
                actor_name=user.username or user.email,
                context={"chat_id": chat_id, "chat_name": chat.name},
            )
        logger.info("Chat locked.", extra={"chat_id": chat_id, "user_id": user.id})

    def unlock_chat(self, user: AuthenticatedUser, chat_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({LOCK_CHAT}))
        with transaction.atomic():
            chat = chat_repository.get_by_id_for_update(chat_id)
            if chat is None:
                raise ChatNotFoundException()
            self._require_owner_or_creator(chat, user, "unlock")
            chat_repository.update(chat, updated_by=user.id, is_locked=False)
        _broadcast_chat_locked_changed(chat_id, is_locked=False, by=user.id)
        logger.info("Chat unlocked.", extra={"chat_id": chat_id, "user_id": user.id})

    def clear_content(self, user: AuthenticatedUser, chat_id: int) -> None:
        from apps.artifact.services.artifact_service import clear_chat_artifacts

        AccessControl.require_permissions(user, frozenset({CLEAR_CHAT_HISTORY}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if not membership_repository.is_chat_owner(chat_id, user.id):
            from apps.artifact_message.exceptions import NotChatOwnerException
            raise NotChatOwnerException()

        # Hold the per-chat AI reply lock while clearing so an in-flight
        # generation cannot re-create a message right after we wipe the history.
        lock_token = _try_acquire_ai_lock(chat_id)
        if not lock_token:
            raise ChatAiReplyInProgressException(
                detail="Cannot clear history while the assistant is replying. Try again shortly."
            )
        try:
            with transaction.atomic():
                clear_chat_artifacts(chat_id, deleted_by=user.id)
                transaction.on_commit(
                    lambda: _broadcast_chat_content_cleared(chat_id, user.id)
                )
        finally:
            _release_ai_lock(chat_id, lock_token)
        logger.info("Chat content cleared.", extra={"chat_id": chat_id, "user_id": user.id})

    def mark_as_read(self, user: AuthenticatedUser, chat_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({MARK_CHAT_AS_READ}))
        if not membership_repository.is_active_member(chat_id, user.id):
            raise ChatAccessDeniedException()
        membership_repository.mark_as_read(chat_id, user.id)


chat_service = ChatService()
