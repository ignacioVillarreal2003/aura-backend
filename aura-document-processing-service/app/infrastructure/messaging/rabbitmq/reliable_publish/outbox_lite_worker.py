import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.types import UserId
from app.infrastructure.messaging.rabbitmq.dtos.commands.document_ingestion_command import DocumentIngestionCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_settings import RabbitMQManagerSettings
from app.infrastructure.messaging.rabbitmq.reliable_publish.redis_outbox_lite import RedisOutboxLite
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import DatabaseManagerInterface
from app.infrastructure.persistence.database.repositories.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.memory_database.redis_client.redis_client_settings import RedisClientSettings

logger = logging.getLogger(__name__)


class OutboxLiteWorker:
    def __init__(
            self,
            *,
            outbox: RedisOutboxLite,
            database_manager: DatabaseManagerInterface,
            document_repository: DocumentRepositoryInterface,
            rabbitmq_settings: RabbitMQManagerSettings,
            settings: Optional[RedisClientSettings] = None,
    ) -> None:
        self._outbox = outbox
        self._database_manager = database_manager
        self._document_repository = document_repository
        self._rabbitmq_settings = rabbitmq_settings
        self._settings = settings or RedisClientSettings()
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="outbox-lite-worker")
        logger.info("Outbox-lite background worker started.")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Outbox-lite background worker stopped.")

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._outbox.drain_pending_batch(limit=self._settings.outbox_retry_batch_size)
                await self._reconcile_document_ingestion()
            except Exception:
                logger.exception("Outbox-lite worker loop iteration failed.")
            await asyncio.sleep(self._settings.outbox_worker_loop_interval_seconds)

    async def _reconcile_document_ingestion(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=self._settings.outbox_document_reconcile_age_seconds
        )
        async with self._database_manager.session() as session:
            documents = await self._document_repository.get_stale_uploaded_documents(
                created_before=cutoff,
                limit=self._settings.outbox_document_reconcile_batch_size,
                database_session=session,
            )

        for document in documents:
            aggregate_id = str(document.id)
            already_published = await self._outbox.has_been_published(
                event_type="document_ingestion",
                aggregate_id=aggregate_id,
            )
            if already_published:
                continue

            system_principal = AuthenticatedUser(id=UserId(int(document.created_by)))
            command = DocumentIngestionCommand(
                document_id=document.id,
                storage_url=document.storage_url,
                filename=document.name,
                mime_type=document.mime_type.value if hasattr(document.mime_type, "value") else str(document.mime_type),
                created_by=document.created_by,
                user=system_principal.model_dump(mode="json"),
                prefer_docling=True,
            )
            envelope = MessageEnvelope.wrap(command)
            await self._outbox.publish_or_enqueue(
                event_id=envelope.message_id,
                event_type="document_ingestion",
                aggregate_id=aggregate_id,
                routing_key=self._rabbitmq_settings.document_ingestion_queue,
                body=envelope.to_bytes(),
                headers={"message_id": envelope.message_id},
            )
