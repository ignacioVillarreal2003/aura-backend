import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import select

from app.domain.constants.document.document_status import DocumentStatus
from app.infrastructure.messaging.rabbitmq.dtos.commands.document_ingestion_command import DocumentIngestionCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_settings import RabbitMQManagerSettings
from app.infrastructure.messaging.rabbitmq.reliable_publish.redis_outbox_lite import RedisOutboxLite
from app.infrastructure.persistence.database.database_manager.database_manager_interface import DatabaseManagerInterface
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.memory_database.document_post_process_job_progress_store.document_post_process_job_progress_store_interface import (
    DocumentPostProcessJobProgressStoreInterface,
)
from app.infrastructure.persistence.memory_database.fragment_post_process_job_progress_store.fragment_post_process_job_progress_store_interface import (
    FragmentPostProcessJobProgressStoreInterface,
)
from app.infrastructure.persistence.memory_database.redis_client.redis_client_settings import RedisClientSettings

logger = logging.getLogger(__name__)


class OutboxLiteWorker:
    def __init__(
            self,
            *,
            outbox: RedisOutboxLite,
            database_manager: DatabaseManagerInterface,
            document_job_progress_store: DocumentPostProcessJobProgressStoreInterface,
            fragment_job_progress_store: FragmentPostProcessJobProgressStoreInterface,
            rabbitmq_settings: RabbitMQManagerSettings,
            settings: Optional[RedisClientSettings] = None,
    ) -> None:
        self._outbox = outbox
        self._database_manager = database_manager
        self._document_job_progress_store = document_job_progress_store
        self._fragment_job_progress_store = fragment_job_progress_store
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
                await self._reconcile_post_process_jobs()
            except Exception:
                logger.exception("Outbox-lite worker loop iteration failed.")
            await asyncio.sleep(self._settings.outbox_worker_loop_interval_seconds)

    async def _reconcile_document_ingestion(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=self._settings.outbox_document_reconcile_age_seconds
        )
        async with self._database_manager.session() as session:
            result = await session.execute(
                select(Document).where(
                    Document.deleted_at.is_(None),
                    Document.status == DocumentStatus.uploaded.value,
                    Document.created_at <= cutoff,
                ).order_by(Document.created_at.asc()).limit(self._settings.outbox_document_reconcile_batch_size)
            )
            documents = list(result.scalars().all())

        for document in documents:
            aggregate_id = str(document.id)
            already_published = await self._outbox.has_been_published(
                event_type="document_ingestion",
                aggregate_id=aggregate_id,
            )
            if already_published:
                continue

            command = DocumentIngestionCommand(
                document_id=document.id,
                storage_url=document.storage_url,
                filename=document.name,
                mime_type=document.mime_type.value if hasattr(document.mime_type, "value") else str(document.mime_type),
                created_by=document.created_by,
                prefer_docling=False,
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

    async def _reconcile_post_process_jobs(self) -> None:
        document_snapshot = await self._document_job_progress_store.get_document_job_snapshot()
        if document_snapshot and bool(document_snapshot.get("is_running")):
            job_id = str(document_snapshot.get("job_id") or "")
            if job_id:
                await self._ensure_post_process_job_pending(
                    event_type="post_process_document",
                    routing_key=self._rabbitmq_settings.post_process_document_queue,
                    job_id=job_id,
                )

        fragment_snapshot = await self._fragment_job_progress_store.get_fragment_job_snapshot()
        if fragment_snapshot and bool(fragment_snapshot.get("is_running")):
            job_id = str(fragment_snapshot.get("job_id") or "")
            if job_id:
                await self._ensure_post_process_job_pending(
                    event_type="post_process_fragment",
                    routing_key=self._rabbitmq_settings.post_process_fragment_queue,
                    job_id=job_id,
                )

    async def _ensure_post_process_job_pending(
            self,
            *,
            event_type: str,
            routing_key: str,
            job_id: str,
    ) -> None:
        if await self._outbox.has_been_published(event_type=event_type, aggregate_id=job_id):
            return

        if event_type == "post_process_document":
            from app.infrastructure.messaging.rabbitmq.dtos.commands.post_process_document_job_command import (
                PostProcessDocumentJobCommand,
            )
            envelope = MessageEnvelope.wrap(PostProcessDocumentJobCommand(job_id=job_id))
        else:
            from app.infrastructure.messaging.rabbitmq.dtos.commands.post_process_fragment_job_command import (
                PostProcessFragmentJobCommand,
            )
            envelope = MessageEnvelope.wrap(PostProcessFragmentJobCommand(job_id=job_id))

        await self._outbox.publish_or_enqueue(
            event_id=envelope.message_id,
            event_type=event_type,
            aggregate_id=job_id,
            routing_key=routing_key,
            body=envelope.to_bytes(),
            headers={
                "message_id": envelope.message_id,
                "correlation_id": job_id,
            },
        )
