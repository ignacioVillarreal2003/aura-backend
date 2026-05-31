from django.db.models import QuerySet

from apps.membership.repositories.membership_repository import membership_repository
from apps.message.exceptions import MessageAccessDeniedException, MessageNotFoundException
from apps.message.models.message_thread_reply import MessageThreadReply
from apps.message.repositories.message_repository import message_repository
from apps.message.repositories.thread_repository import thread_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import ADD_THREAD_REPLY, LIST_THREAD_REPLIES


class ThreadService:
    def get_thread(
            self, user: AuthenticatedUser, chat_id: int, message_id: int
    ) -> QuerySet[MessageThreadReply]:
        AccessControl.require_permissions(user, frozenset({LIST_THREAD_REPLIES}))
        if not membership_repository.is_active_member(chat_id, user.id):
            raise MessageAccessDeniedException()
        msg = message_repository.get_by_id_and_chat(message_id, chat_id)
        if msg is None:
            raise MessageNotFoundException()
        return thread_repository.get_by_message(message_id)

    def add_reply(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            message_id: int,
            message_text: str,
    ) -> MessageThreadReply:
        AccessControl.require_permissions(user, frozenset({ADD_THREAD_REPLY}))
        if not membership_repository.is_active_member(chat_id, user.id):
            raise MessageAccessDeniedException()
        msg = message_repository.get_by_id_and_chat(message_id, chat_id)
        if msg is None:
            raise MessageNotFoundException()
        return thread_repository.create(
            parent_message_id=message_id,
            message=message_text,
            created_by=user.id,
        )


thread_service = ThreadService()
