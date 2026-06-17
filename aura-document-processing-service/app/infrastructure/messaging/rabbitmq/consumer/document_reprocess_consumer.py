import logging
import uuid
from typing import Optional
import redis.asyncio as aioredis

from app.application.services.document.reprocess_document_service.interfaces.reprocess_document_service_interface import (
    ReprocessDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.messaging.rabbitmq.consumer.base_consumer import BaseConsumer
from app.infrastructure.messaging.rabbitmq.consumer.interfaces.document_reprocess_consumer_interface import (
    DocumentReprocessConsumerInterface,
)
from app.infrastructure.messaging.rabbitmq.dtos.commands.document_reprocess_command import DocumentReprocessCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_interface import RabbitMQManagerInterface

logger = logging.getLogger(__name__)

_RELEASE_LOCK_SCRIPT = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then return redis.call('del', KEYS[1]) "
    "else return 0 end"
)


class DocumentReprocessConsumer(BaseConsumer[DocumentReprocessCommand], DocumentReprocessConsumerInterface):
    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            reprocess_document_service: ReprocessDocumentServiceInterface,
            redis_client: aioredis.Redis,
    ) -> None:
        super().__init__(rabbitmq_manager)
        self._service = reprocess_document_service
        self._redis = redis_client

    @property
    def _queue_name(self) -> str:
        return self._settings.document_reprocess_queue

    @property
    def _prefetch_count(self) -> Optional[int]:
        return 1

    def _get_command_type(self) -> type[DocumentReprocessCommand]:
        return DocumentReprocessCommand

    async def _process(self, envelope: MessageEnvelope[DocumentReprocessCommand]) -> None:
        command = envelope.command
        document_id = command.document_id
        user = AuthenticatedUser.model_validate(command.user)

        # Share the ingestion lock so reprocess cannot run concurrently with an
        # in-flight ingestion/re-embed of the same document.
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
                post_process=command.post_process,
                post_process_graph=command.post_process_graph,
            )
            logger.info(
                "The document-reprocess message was processed.",
                extra={"message_id": envelope.message_id, "document_id": document_id, "user_id": user.id},
            )
        finally:
            # redis-py types eval() as returning ResponseT (Awaitable | Any); on the
            # async client it is always awaitable.
            await self._redis.eval(_RELEASE_LOCK_SCRIPT, 1, lock_key, lock_token)  # type: ignore[misc]

    def _build_document_lock_key(self, document_id: int) -> str:
        return f"{self._settings.document_ingestion_lock_key_prefix}:document:{document_id}:lock"
