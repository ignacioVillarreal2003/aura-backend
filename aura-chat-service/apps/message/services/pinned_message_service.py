import logging

from django.db.models import QuerySet

from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.exceptions import MessageAccessDeniedException, MessageNotFoundException
from apps.message.models.pinned_message import PinnedMessage
from apps.message.repositories.message_repository import message_repository
from apps.message.repositories.pinned_message_repository import pinned_message_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import LIST_MESSAGES

logger = logging.getLogger(__name__)


class PinnedMessageService:
    def list_pinned(self, user: AuthenticatedUser, chat_id: int) -> QuerySet[PinnedMessage]:
        AccessControl.require_permissions(user, frozenset({LIST_MESSAGES}))
        if not membership_repository.is_active_member(chat_id, user.id):
            raise MessageAccessDeniedException()
        return pinned_message_repository.list_by_chat(chat_id)

    def pin_message(self, user: AuthenticatedUser, chat_id: int, message_id: int) -> PinnedMessage:
        AccessControl.require_permissions(user, frozenset({LIST_MESSAGES}))
        if not membership_repository.is_active_member(chat_id, user.id):
            raise MessageAccessDeniedException()
        msg = message_repository.get_by_id_and_chat(message_id, chat_id)
        if msg is None:
            raise MessageNotFoundException()
        pin, _ = pinned_message_repository.pin(message_id, chat_id, pinned_by=user.id)
        logger.info("Message pinned.", extra={"chat_id": chat_id, "message_id": message_id, "user_id": user.id})
        return pin

    def unpin_message(self, user: AuthenticatedUser, chat_id: int, message_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({LIST_MESSAGES}))
        if not membership_repository.is_active_member(chat_id, user.id):
            raise MessageAccessDeniedException()
        pinned_message_repository.unpin(message_id, chat_id)
        logger.info("Message unpinned.", extra={"chat_id": chat_id, "message_id": message_id, "user_id": user.id})


pinned_message_service = PinnedMessageService()
