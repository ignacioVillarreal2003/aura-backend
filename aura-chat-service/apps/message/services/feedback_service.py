from apps.membership.repositories.membership_repository import membership_repository
from apps.message.exceptions import (
    MessageAccessDeniedException,
    MessageNotFoundException,
    NotAIMessageException,
)
from apps.message.models.chat_message import ChatMessage
from apps.message.models.message_feedback import MessageFeedback
from apps.message.repositories.feedback_repository import feedback_repository
from apps.message.repositories.message_repository import message_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import SET_MESSAGE_FEEDBACK


def _require_ai_message(user_id: int, chat_id: int, message_id: int) -> ChatMessage:
    if not membership_repository.is_active_member(chat_id, user_id):
        raise MessageAccessDeniedException()
    msg = message_repository.get_by_id_and_chat(message_id, chat_id)
    if msg is None:
        raise MessageNotFoundException()
    if msg.sender_type != ChatMessage.SenderType.SYSTEM:
        raise NotAIMessageException()
    return msg


class FeedbackService:
    def set_feedback(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            message_id: int,
            value: int,
    ) -> MessageFeedback:
        AccessControl.require_permissions(user, frozenset({SET_MESSAGE_FEEDBACK}))
        _require_ai_message(user.id, chat_id, message_id)
        return feedback_repository.set(message_id=message_id, user_id=user.id, value=value)

    def delete_feedback(
            self, user: AuthenticatedUser, chat_id: int, message_id: int
    ) -> None:
        AccessControl.require_permissions(user, frozenset({SET_MESSAGE_FEEDBACK}))
        _require_ai_message(user.id, chat_id, message_id)
        feedback_repository.delete(message_id=message_id, user_id=user.id)


feedback_service = FeedbackService()
