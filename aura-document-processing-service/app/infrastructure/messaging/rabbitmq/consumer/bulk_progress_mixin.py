import logging
from typing import Any, Optional

from app.domain.constants.document.bulk_operation import BulkOperation
from app.domain.field_limits import MAX_POST_PROCESS_ERROR_MESSAGE_CHARS
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.persistence.memory_database.bulk_job_progress_store.interfaces.bulk_job_progress_store_interface import (
    BulkJobProgressStoreInterface,
)

logger = logging.getLogger(__name__)


class BulkProgressMixin:
    _bulk_operation: BulkOperation
    _bulk_store: Optional[BulkJobProgressStoreInterface]

    async def _execute(self, envelope: MessageEnvelope[Any]) -> None:  # pragma: no cover
        raise NotImplementedError

    async def _process(self, envelope: MessageEnvelope[Any]) -> None:
        batch_id = getattr(envelope.command, "batch_id", None)
        store = self._bulk_store
        if not batch_id or store is None:
            await self._execute(envelope)
            return

        operation = self._bulk_operation
        if await store.is_stopped(operation=operation, job_id=batch_id):
            await store.mark(operation=operation, job_id=batch_id, processed_increment=1)
            return

        try:
            await self._execute(envelope)
            await store.mark(operation=operation, job_id=batch_id, processed_increment=1)
        except Exception as exc:
            document_id = getattr(envelope.command, "document_id", None)
            await store.mark(operation=operation, job_id=batch_id, failed_increment=1)
            await store.append_error(
                operation=operation,
                job_id=batch_id,
                error={
                    "document_id": document_id,
                    "error": str(exc)[:MAX_POST_PROCESS_ERROR_MESSAGE_CHARS],
                },
            )
            logger.warning(
                "A bulk item failed; recorded in the job and acknowledged.",
                extra={
                    "operation": operation.value,
                    "job_id": batch_id,
                    "document_id": document_id,
                },
            )
