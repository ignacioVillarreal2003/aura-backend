import logging
import tempfile
import uuid
from pathlib import Path
import aio_pika.abc

from app.application.services.document.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface
)
from app.infrastructure.messaging.rabbitmq.dtos.commands.document_ingestion_command import DocumentIngestionCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.interfaces.rabbitmq_manager_interface import RabbitMQManagerInterface
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface,
)

logger = logging.getLogger(__name__)


class DocumentIngestionConsumer:
    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            document_storage: DocumentStorageInterface,
            database_manager: DatabaseManagerInterface,
            document_repository: DocumentRepositoryInterface,
            document_ingestion_service: DocumentIngestionServiceInterface,
    ) -> None:
        self._manager = rabbitmq_manager
        self._settings = rabbitmq_manager.settings
        self._document_storage = document_storage
        self._database_manager = database_manager
        self._document_repository = document_repository
        self._document_ingestion_service = document_ingestion_service

    async def start(self) -> None:
        await self._manager.start_consumer(
            queue_name=self._settings.document_ingestion_queue,
            callback=self._handle_message,
        )
        logger.info(
            "DocumentIngestionConsumer registered",
            extra={"queue": self._settings.document_ingestion_queue},
        )

    async def _handle_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        retry_count = self._extract_retry_count(message)

        if retry_count >= self._settings.max_delivery_attempts:
            logger.error(
                "Message exceeded max delivery attempts — discarding permanently",
                extra={
                    "retry_count": retry_count,
                    "max_delivery_attempts": self._settings.max_delivery_attempts,
                    "message_id": (message.headers or {}).get("message_id", "unknown"),
                },
            )
            await message.nack(requeue=False)
            return

        try:
            message_envelope = MessageEnvelope.from_bytes(
                data=message.body,
                command_type=DocumentIngestionCommand,
                retry_count=retry_count,
            )
        except Exception:
            logger.exception(
                "Failed to deserialise message — discarding (malformed payload cannot be retried)",
                extra={"body_preview": message.body[:200]},
            )
            await message.nack(requeue=False)
            return

        try:
            logger.debug(
                "Dispatching message to handler",
                extra={
                    "message_id": message_envelope.message_id,
                    "document_id": message_envelope.command.document_id,
                    "retry_count": retry_count,
                },
            )
            await self.handle(message_envelope)
            await message.ack()
            logger.info(
                "Message processed successfully",
                extra={
                    "message_id": message_envelope.message_id,
                    "document_id": message_envelope.command.document_id,
                },
            )

        except Exception:
            logger.exception(
                "Handler raised an error — NACKing for DLX retry",
                extra={
                    "message_id": message_envelope.message_id,
                    "document_id": message_envelope.command.document_id,
                    "retry_count": retry_count,
                },
            )
            await message.nack(requeue=False)

    @staticmethod
    def _extract_retry_count(message: aio_pika.abc.AbstractIncomingMessage) -> int:
        if not message.headers:
            return 0
        x_death = message.headers.get("x-death")
        if not x_death:
            return 0
        try:
            return int(sum(entry.get("count", 0) for entry in x_death))
        except Exception:
            logger.warning("Could not parse x-death header", extra={"x_death": str(x_death)})
            return 0

    async def handle(self, message_envelope: MessageEnvelope[DocumentIngestionCommand]) -> None:
        document_ingestion_command = message_envelope.command
        document_id = document_ingestion_command.document_id

        logger.info(
            "Handling document ingestion from queue",
            extra={
                "message_id": message_envelope.message_id,
                "document_id": document_id,
            },
        )

        temp_dir = Path(tempfile.gettempdir()) / "doc_ingestion"
        temp_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(document_ingestion_command.filename).name
        temp_path = temp_dir / f"{uuid.uuid4().hex}_{safe_name}"

        await self._document_storage.download_document_to_file(
            object_name=document_ingestion_command.storage_url,
            file_path=str(temp_path),
        )

        logger.info(
            "Document downloaded from storage for ingestion",
            extra={
                "document_id": document_id,
                "storage_url": document_ingestion_command.storage_url,
            },
        )

        async with self._database_manager.session() as db_session:
            document = await self._document_repository.get_document_by_id(
                document_id=document_id,
                database_session=db_session,
            )
            if document is not None:
                await db_session.refresh(document)
                db_session.expunge(document)

        if document is None:
            logger.error(
                "Document not found in database — acknowledging to drop poison message",
                extra={"document_id": document_id},
            )
            return

        await self._document_ingestion_service.process_document(
            document=document,
            local_file_path=temp_path,
            prefer_docling=document_ingestion_command.prefer_docling,
        )

        logger.info(
            "Document ingestion pipeline finished",
            extra={"document_id": document_id},
        )
