import logging

from django.db.models import QuerySet

from apps.message.models.chat_message import ChatMessage

logger = logging.getLogger(__name__)


class MessageRepository:

    @staticmethod
    def create(
        chat_id: int,
        message: str,
        sender_type: str,
        created_by: int,
    ) -> ChatMessage:
        return ChatMessage.objects.create(
            chat_id=chat_id,
            message=message,
            sender_type=sender_type,
            created_by=created_by,
        )

    @staticmethod
    def get_messages_by_chat(chat_id: int) -> QuerySet[ChatMessage]:
        return ChatMessage.objects.filter(chat_id=chat_id)

    @staticmethod
    def get_recent_messages(chat_id: int, limit: int = 20) -> list[ChatMessage]:
        return list(
            ChatMessage.objects
            .filter(chat_id=chat_id)
            .order_by("-created_at")[:limit]
        )


message_repository = MessageRepository()
