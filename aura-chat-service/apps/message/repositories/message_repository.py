import logging
from django.db.models import CharField, Count, Exists, IntegerField, OuterRef, QuerySet, SmallIntegerField, Subquery
from django.db.models.functions import Coalesce

from apps.message.models.chat_message import ChatMessage

logger = logging.getLogger(__name__)


class MessageRepository:
    @staticmethod
    def create(
        chat_id: int,
        message: str,
        sender_type: str,
        created_by: int,
        fragments: list | None = None,
    ) -> ChatMessage:
        return ChatMessage.objects.create(
            chat_id=chat_id,
            message=message,
            sender_type=sender_type,
            created_by=created_by,
            fragments=fragments or None,
        )

    @staticmethod
    def get_messages_by_chat(chat_id: int, user_id: int | None = None) -> QuerySet[ChatMessage]:
        from apps.message.models.message_bookmark import MessageBookmark
        from apps.message.models.message_feedback import MessageFeedback
        from apps.message.models.message_thread_reply import MessageThreadReply

        qs = ChatMessage.objects.filter(chat_id=chat_id)

        if user_id is not None:
            qs = qs.annotate(
                is_bookmarked=Exists(
                    MessageBookmark.objects.filter(
                        message_id=OuterRef("pk"),
                        user_id=user_id,
                    )
                ),
                user_feedback=Subquery(
                    MessageFeedback.objects.filter(
                        message_id=OuterRef("pk"),
                        user_id=user_id,
                    ).values("value")[:1],
                    output_field=SmallIntegerField(),
                ),
                user_feedback_reason=Subquery(
                    MessageFeedback.objects.filter(
                        message_id=OuterRef("pk"),
                        user_id=user_id,
                    ).values("reason")[:1],
                    output_field=CharField(),
                ),
                user_feedback_comment=Subquery(
                    MessageFeedback.objects.filter(
                        message_id=OuterRef("pk"),
                        user_id=user_id,
                    ).values("comment")[:1],
                    output_field=CharField(),
                ),
                thread_reply_count=Coalesce(
                    Subquery(
                        MessageThreadReply.objects.filter(parent_message_id=OuterRef("pk"))
                        .values("parent_message_id")
                        .annotate(c=Count("id"))
                        .values("c")[:1],
                        output_field=IntegerField(),
                    ),
                    0,
                ),
            )

        return qs

    @staticmethod
    def get_recent_messages(chat_id: int, limit: int = 10) -> list[ChatMessage]:
        return list(
            ChatMessage.objects
            .filter(chat_id=chat_id)
            .order_by("-created_at")[:limit]
        )

    @staticmethod
    def get_last_ai_message(chat_id: int) -> ChatMessage | None:
        return (
            ChatMessage.objects
            .filter(chat_id=chat_id, sender_type=ChatMessage.SenderType.SYSTEM)
            .order_by("-created_at")
            .first()
        )

    @staticmethod
    def get_by_id_and_chat(message_id: int, chat_id: int) -> ChatMessage | None:
        return ChatMessage.objects.filter(id=message_id, chat_id=chat_id).first()

    @staticmethod
    def soft_delete_by_chat(chat_id: int, deleted_by: int) -> None:
        ChatMessage.objects.filter(chat_id=chat_id).delete(deleted_by=deleted_by)


message_repository = MessageRepository()
