from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.exceptions import MessageAccessDeniedException, MessageNotFoundException
from apps.message.models.chat_message import ChatMessage
from apps.message.repositories.bookmark_repository import bookmark_repository
from apps.message.repositories.message_repository import message_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import LIST_MESSAGES


def _require_message_access(user_id: int, chat_id: int, message_id: int) -> ChatMessage:
    if not membership_repository.is_active_member(chat_id, user_id):
        raise MessageAccessDeniedException()
    msg = message_repository.get_by_id_and_chat(message_id, chat_id)
    if msg is None:
        raise MessageNotFoundException()
    return msg


class BookmarkService:
    def bookmark(self, user: AuthenticatedUser, chat_id: int, message_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({LIST_MESSAGES}))
        _require_message_access(user.id, chat_id, message_id)
        bookmark_repository.create(message_id=message_id, user_id=user.id)

    def unbookmark(self, user: AuthenticatedUser, chat_id: int, message_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({LIST_MESSAGES}))
        _require_message_access(user.id, chat_id, message_id)
        bookmark_repository.delete(message_id=message_id, user_id=user.id)

    def list_bookmarked(self, user: AuthenticatedUser, chat_id: int):
        AccessControl.require_permissions(user, frozenset({LIST_MESSAGES}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id, user.id):
            raise MessageAccessDeniedException()
        ids = bookmark_repository.get_bookmarked_message_ids(chat_id, user.id)
        return message_repository.get_messages_by_chat(chat_id, user_id=user.id).filter(id__in=ids)


bookmark_service = BookmarkService()
