import logging
import tempfile
import uuid
from pathlib import Path
from typing import Optional
import redis.asyncio as aioredis

from app.application.services.document.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.document_status import DocumentStatus
from app.infrastructure.messaging.rabbitmq.consumer.base_consumer import BaseConsumer
from app.infrastructure.messaging.rabbitmq.consumer.interfaces.document_ingestion_consumer_interface import (
    DocumentIngestionConsumerInterface,
)
from app.infrastructure.messaging.rabbitmq.dtos.commands.document_ingestion_command import DocumentIngestionCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.interfaces.rabbitmq_manager_interface import RabbitMQManagerInterface
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.repositories.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface,
)

logger = logging.getLogger(__name__)

_RELEASE_LOCK_SCRIPT = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then return redis.call('del', KEYS[1]) "
    "else return 0 end"
)


class DocumentIngestionConsumer(BaseConsumer[DocumentIngestionCommand], DocumentIngestionConsumerInterface):
    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            document_storage: DocumentStorageInterface,
            database_manager: DatabaseManagerInterface,
            document_repository: DocumentRepositoryInterface,
            document_ingestion_service: DocumentIngestionServiceInterface,
            redis_client: aioredis.Redis,
    ) -> None:
        super().__init__(rabbitmq_manager)
        self._document_storage = document_storage
        self._database_manager = database_manager
        self._document_repository = document_repository
        self._document_ingestion_service = document_ingestion_service
        self._redis = redis_client

    @property
    def _queue_name(self) -> str:
        return self._settings.document_ingestion_queue

    def _get_command_type(self) -> type[DocumentIngestionCommand]:
        return DocumentIngestionCommand

    async def _process(self, envelope: MessageEnvelope[DocumentIngestionCommand]) -> None:
        await self.handle(envelope)

    async def handle(
            self,
            message_envelope: MessageEnvelope[DocumentIngestionCommand]
    ) -> None:
        document_ingestion_command = message_envelope.command
        document_id = document_ingestion_command.document_id
        lock_key = self._build_document_lock_key(document_id)
        lock_token = f"{message_envelope.message_id}:{uuid.uuid4().hex}"
        lock_acquired = False
        temp_path: Optional[Path] = None

        logger.info(
            "Starting document ingestion for a message from the queue.",
            extra={
                "message_id": message_envelope.message_id,
                "document_id": document_id
            }
        )

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
                "Skipping duplicate/redelivered ingestion message because document lock is active.",
                extra={
                    "document_id": document_id,
                    "message_id": message_envelope.message_id,
                },
            )
            return

        try:
            temp_dir = Path(tempfile.gettempdir()) / self._settings.document_ingestion_temp_dir_name
            temp_dir.mkdir(parents=True, exist_ok=True)
            safe_name = Path(document_ingestion_command.filename).name
            temp_path = temp_dir / f"{uuid.uuid4().hex}_{safe_name}"

            await self._document_storage.download_document_to_file(
                object_name=document_ingestion_command.storage_url,
                file_path=str(temp_path)
            )

            logger.info(
                "The document file was downloaded from object storage for ingestion.",
                extra={
                    "document_id": document_id
                }
            )

            async with self._database_manager.session() as db_session:
                document = await self._document_repository.get_document_by_id(
                    document_id=document_id,
                    database_session=db_session
                )
                if document is not None:
                    await db_session.refresh(document)
                    db_session.expunge(document)

            if document is None:
                logger.error(
                    "No document row was found for the given id; acknowledging to drop a poison message.",
                    extra={
                        "document_id": document_id
                    }
                )
                return

            status = document.status if isinstance(document.status, DocumentStatus) else DocumentStatus(document.status)
            if status in {DocumentStatus.processed, DocumentStatus.failed}:
                logger.info(
                    "Skipping ingestion because document is already in a terminal status.",
                    extra={
                        "document_id": document_id,
                        "status": status.value,
                    },
                )
                return

            user = AuthenticatedUser.model_validate(document_ingestion_command.user)
            await self._document_ingestion_service.process_document(
                document=document,
                local_file_path=temp_path,
                user=user,
                prefer_docling=document_ingestion_command.prefer_docling,
                enrich=document_ingestion_command.enrich,
                graph_extract=document_ingestion_command.graph_extract,
            )

            logger.info(
                "The document ingestion pipeline finished successfully.",
                extra={
                    "document_id": document_id
                }
            )
        finally:
            if temp_path is not None:
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except Exception:
                    logger.warning(
                        "Failed to cleanup ingestion temporary file in consumer finally block.",
                        extra={"document_id": document_id, "path": str(temp_path)},
                    )
            if lock_acquired:
                await self._release_document_lock(lock_key, lock_token)

    def _build_document_lock_key(self, document_id: int) -> str:
        return f"{self._settings.document_ingestion_lock_key_prefix}:document:{document_id}:lock"

    async def _release_document_lock(self, lock_key: str, lock_token: str) -> None:
        await self._redis.eval(_RELEASE_LOCK_SCRIPT, 1, lock_key, lock_token)
