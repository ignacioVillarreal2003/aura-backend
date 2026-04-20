import json
import logging
import tempfile
import uuid
from pathlib import Path

import aio_pika.abc
from pydantic import ValidationError

from app.application.services.document.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface
)
from app.infrastructure.messaging.rabbitmq.dtos.commands.document_ingestion_command import DocumentIngestionCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_interface import RabbitMQManagerInterface
from app.infrastructure.persistence.database.database_manager.database_manager_interface import (
    DatabaseManagerInterface
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.storages.document_storage.document_storage_interface import (
    DocumentStorageInterface
)

logger = logging.getLogger(__name__)


class DocumentIngestionConsumer:
    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            document_storage: DocumentStorageInterface,
            database_manager: DatabaseManagerInterface,
            document_repository: DocumentRepositoryInterface,
            document_ingestion_service: DocumentIngestionServiceInterface
    ) -> None:
        self._manager = rabbitmq_manager
        self._settings = rabbitmq_manager.settings
        self._document_storage = document_storage
        self._database_manager = database_manager
        self._document_repository = document_repository
        self._document_ingestion_service = document_ingestion_service

    async def start(
            self
    ) -> None:
        await self._manager.start_consumer(
            queue_name=self._settings.document_ingestion_queue,
            callback=self._handle_message
        )
        logger.info(
            "The document ingestion consumer was registered on the queue.",
            extra={
                "queue": self._settings.document_ingestion_queue
            }
        )

    async def _handle_message(
            self,
            message: aio_pika.abc.AbstractIncomingMessage
    ) -> None:
        retry_count = self._extract_retry_count(message)

        if retry_count >= self._settings.max_delivery_attempts:
            logger.error(
                "A message exceeded the maximum delivery attempts and will be discarded.",
                extra={
                    "retry_count": retry_count,
                    "max_delivery_attempts": self._settings.max_delivery_attempts,
                    "message_id": (message.headers or {}).get("message_id", "unknown")
                }
            )
            await message.nack(requeue=False)
            return

        body = message.body
        body_len = len(body)
        if body_len > self._settings.max_message_body_bytes:
            logger.error(
                "The message body exceeded the configured maximum size; discarding without requeue.",
                extra={
                    "message_id": (message.headers or {}).get("message_id", "unknown"),
                    "body_bytes": body_len,
                    "max_message_body_bytes": self._settings.max_message_body_bytes,
                },
            )
            await message.nack(requeue=False)
            return

        try:
            message_envelope = MessageEnvelope.from_bytes(
                data=body,
                command_type=DocumentIngestionCommand,
                retry_count=retry_count
            )
        except UnicodeDecodeError as e:
            logger.error(
                "The message body was not valid UTF-8; discarding without requeue.",
                extra={
                    "message_id": (message.headers or {}).get("message_id", "unknown"),
                    "error": type(e).__name__,
                },
            )
            await message.nack(requeue=False)
            return
        except json.JSONDecodeError as e:
            logger.error(
                "The message body was not valid JSON; discarding without requeue.",
                extra={
                    "message_id": (message.headers or {}).get("message_id", "unknown"),
                    "error": type(e).__name__,
                },
            )
            await message.nack(requeue=False)
            return
        except ValidationError as e:
            logger.error(
                "The message envelope failed schema validation; discarding without requeue.",
                extra={
                    "message_id": (message.headers or {}).get("message_id", "unknown"),
                    "error": type(e).__name__,
                    "error_count": len(e.errors()),
                },
            )
            await message.nack(requeue=False)
            return

        try:
            logger.debug(
                "Dispatching a queue message to the ingestion handler.",
                extra={
                    "message_id": message_envelope.message_id,
                    "document_id": message_envelope.command.document_id,
                    "retry_count": retry_count
                }
            )
            await self.handle(message_envelope)
            await message.ack()
            logger.info(
                "The queue message was processed successfully.",
                extra={
                    "message_id": message_envelope.message_id,
                    "document_id": message_envelope.command.document_id
                }
            )

        except Exception:
            logger.exception(
                "The ingestion handler failed; the message will be negative-acknowledged for dead-letter retry.",
                extra={
                    "message_id": message_envelope.message_id,
                    "document_id": message_envelope.command.document_id,
                    "retry_count": retry_count
                }
            )
            await message.nack(requeue=False)

    @staticmethod
    def _extract_retry_count(
            message: aio_pika.abc.AbstractIncomingMessage
    ) -> int:
        if not message.headers:
            return 0
        x_death = message.headers.get("x-death")
        if not x_death:
            return 0
        try:
            return int(sum(entry.get("count", 0) for entry in x_death))
        except Exception:
            logger.warning("The x-death header could not be parsed; treating retry count as zero.")
            return 0

    async def handle(
            self,
            message_envelope: MessageEnvelope[DocumentIngestionCommand]
    ) -> None:
        document_ingestion_command = message_envelope.command
        document_id = document_ingestion_command.document_id

        logger.info(
            "Starting document ingestion for a message from the queue.",
            extra={
                "message_id": message_envelope.message_id,
                "document_id": document_id
            }
        )

        temp_dir = Path(tempfile.gettempdir()) / "doc_ingestion"
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

        await self._document_ingestion_service.process_document(
            document=document,
            local_file_path=temp_path,
            prefer_docling=document_ingestion_command.prefer_docling
        )

        logger.info(
            "The document ingestion pipeline finished successfully.",
            extra={
                "document_id": document_id
            }
        )
