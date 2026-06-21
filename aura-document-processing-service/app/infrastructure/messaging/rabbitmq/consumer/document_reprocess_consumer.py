import logging
import uuid
from typing import Optional
import redis.asyncio as aioredis

from app.application.services.document.reprocess_document_service.interfaces.reprocess_document_service_interface import (
    ReprocessDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.bulk_operation import BulkOperation
from app.infrastructure.messaging.rabbitmq.consumer.base_consumer import BaseConsumer
from app.infrastructure.messaging.rabbitmq.consumer.bulk_progress_mixin import BulkProgressMixin
from app.infrastructure.messaging.rabbitmq.consumer.interfaces.document_reprocess_consumer_interface import (
    DocumentReprocessConsumerInterface,
)
from app.infrastructure.messaging.rabbitmq.dtos.commands.document_reprocess_command import DocumentReprocessCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.interfaces.rabbitmq_manager_interface import RabbitMQManagerInterface
from app.infrastructure.persistence.memory_database.bulk_job_progress_store.interfaces.bulk_job_progress_store_interface import (
    BulkJobProgressStoreInterface,
)

logger = logging.getLogger(__name__)

_RELEASE_LOCK_SCRIPT = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then return redis.call('del', KEYS[1]) "
    "else return 0 end"
)


class DocumentReprocessConsumer(
    BulkProgressMixin,
    BaseConsumer[DocumentReprocessCommand],
    DocumentReprocessConsumerInterface,
):
    _bulk_operation = BulkOperation.reprocess

    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            reprocess_document_service: ReprocessDocumentServiceInterface,
            redis_client: aioredis.Redis,
            bulk_job_progress_store: Optional[BulkJobProgressStoreInterface] = None,
    ) -> None:
        super().__init__(rabbitmq_manager)
        self._service = reprocess_document_service
        self._redis = redis_client
        self._bulk_store = bulk_job_progress_store

    @property
    def _queue_name(self) -> str:
        return self._settings.document_reprocess_queue

    @property
    def _prefetch_count(self) -> Optional[int]:
        return 1

    def _get_command_type(self) -> type[DocumentReprocessCommand]:
        return DocumentReprocessCommand

    async def _execute(self, envelope: MessageEnvelope[DocumentReprocessCommand]) -> None:
        command = envelope.command
        document_id = command.document_id
        user = AuthenticatedUser.model_validate(command.user)

        lock_key = self._build_document_lock_key(document_id)
        lock_token = f"{envelope.message_id}:{uuid.uuid4().hex}"
        lock_acquired = bool(
            await self._redis.set(
                lock_key,
                lock_token,
                nx=True,
                ex=self._settings.document_ingestion_lock_ttl_seconds,
            )
        )
        if not lock_acquired:
            logger.info(
                "Skipping reprocess; the document lock is held by another job.",
                extra={"document_id": document_id, "message_id": envelope.message_id},
            )
            return

        try:
            await self._service.reprocess_document(
                document_id=document_id,
                user=user,
                prefer_docling=command.prefer_docling,
                enrich=command.enrich,
                graph_extract=command.graph_extract,
            )
            logger.info(
                "The document-reprocess message was processed.",
                extra={"message_id": envelope.message_id, "document_id": document_id, "user_id": user.id},
            )
        finally:
            await self._redis.eval(_RELEASE_LOCK_SCRIPT, 1, lock_key, lock_token)  # type: ignore[misc]

    def _build_document_lock_key(self, document_id: int) -> str:
        return f"{self._settings.document_ingestion_lock_key_prefix}:document:{document_id}:lock"
