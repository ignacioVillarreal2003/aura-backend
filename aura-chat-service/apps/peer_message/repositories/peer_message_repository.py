import logging
from django.db.models import QuerySet

from apps.peer_message.models import PeerMessage

logger = logging.getLogger(__name__)


class PeerMessageRepository:
    @staticmethod
    def create(chat_id: int, message: str, created_by: int) -> PeerMessage:
        return PeerMessage.objects.create(
            chat_id=chat_id,
            message=message,
            created_by=created_by,
        )

    @staticmethod
    def get_by_id_and_chat(message_id: int, chat_id: int) -> PeerMessage | None:
        return PeerMessage.objects.filter(pk=message_id, chat_id=chat_id).first()

    @staticmethod
    def list_by_chat(chat_id: int) -> QuerySet[PeerMessage]:
        # ``objects`` already filters out soft-deleted rows (SoftDeleteManager).
        return PeerMessage.objects.filter(chat_id=chat_id)

    @staticmethod
    def soft_delete_by_chat(chat_id: int, deleted_by: int) -> None:
        PeerMessage.objects.filter(chat_id=chat_id).delete(deleted_by=deleted_by)


peer_message_repository = PeerMessageRepository()
