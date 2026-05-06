from django.db.models import QuerySet

from apps.message.models.pinned_message import PinnedMessage


class PinnedMessageRepository:
    @staticmethod
    def pin(message_id: int, chat_id: int, pinned_by: int) -> tuple[PinnedMessage, bool]:
        return PinnedMessage.objects.get_or_create(
            message_id=message_id,
            chat_id=chat_id,
            defaults={"pinned_by": pinned_by},
        )

    @staticmethod
    def unpin(message_id: int, chat_id: int) -> bool:
        deleted, _ = PinnedMessage.objects.filter(
            message_id=message_id,
            chat_id=chat_id,
        ).delete()
        return deleted > 0

    @staticmethod
    def list_by_chat(chat_id: int) -> QuerySet[PinnedMessage]:
        return (
            PinnedMessage.objects.filter(chat_id=chat_id)
            .select_related("message")
            .order_by("pinned_at")
        )

    @staticmethod
    def exists(message_id: int, chat_id: int) -> bool:
        return PinnedMessage.objects.filter(
            message_id=message_id,
            chat_id=chat_id,
        ).exists()


pinned_message_repository = PinnedMessageRepository()
