import asyncio
import logging
import uuid
from typing import Any, Optional

from app.application.services.document.bulk_dispatch_service.exceptions.bulk_dispatch_service_exception import (
    BulkOperationConflictException,
    BulkOperationUnavailableException,
)
from app.application.services.document.bulk_dispatch_service.interfaces.bulk_dispatch_service_interface import (
    BulkDispatchServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.bulk_operation import BulkOperation
from app.domain.dtos.document.bulk.bulk_responses import (
    BulkJobError,
    BulkJobStatusResponse,
    BulkStartResponse,
)
from app.domain.dtos.document.bulk.document_selector import DocumentSelector
from app.domain.field_limits import (
    MAX_POST_PROCESS_DOCUMENT_IDS,
    MAX_POST_PROCESS_ERROR_MESSAGE_CHARS,
)
from app.infrastructure.http.authentication_provider.request_token import (
    get_request_token,
    set_request_token,
)
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.document_enrichment_publisher_interface import (
    DocumentEnrichmentPublisherInterface,
)
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.document_reembed_publisher_interface import (
    DocumentReembedPublisherInterface,
)
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.document_reprocess_publisher_interface import (
    DocumentReprocessPublisherInterface,
)
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.graph_extraction_publisher_interface import (
    GraphExtractionPublisherInterface,
)
from app.infrastructure.persistence.database.database_manager.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.memory_database.bulk_job_progress_store.bulk_job_progress_store_interface import (
    BulkJobProgressStoreInterface,
)

logger = logging.getLogger(__name__)


class BulkDispatchService(BulkDispatchServiceInterface):
    """Fans a maintenance operation out over 1, several or all documents.

    Resolves the target ids (explicit list or the whole corpus), records a job in the
    bulk progress store, and publishes one per-document command per target carrying the
    ``batch_id``. The existing per-document queues (prefetch=1) process them gradually;
    the per-document consumers report back into the same job. The HTTP request returns
    immediately while the fan-out runs in a background task.
    """

    def __init__(
            self,
            *,
            database_manager: DatabaseManagerInterface,
            document_repository: DocumentRepositoryInterface,
            progress_store: BulkJobProgressStoreInterface,
            reembed_publisher: Optional[DocumentReembedPublisherInterface] = None,
            reprocess_publisher: Optional[DocumentReprocessPublisherInterface] = None,
            enrichment_publisher: Optional[DocumentEnrichmentPublisherInterface] = None,
            graph_extraction_publisher: Optional[GraphExtractionPublisherInterface] = None,
    ) -> None:
        self._database_manager = database_manager
        self._document_repository = document_repository
        self._store = progress_store
        self._reembed_publisher = reembed_publisher
        self._reprocess_publisher = reprocess_publisher
        self._enrichment_publisher = enrichment_publisher
        self._graph_extraction_publisher = graph_extraction_publisher
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(
            self,
            *,
            operation: BulkOperation,
            selector: DocumentSelector,
            user: AuthenticatedUser,
            force: bool = False,
            prefer_docling: bool = False,
            post_process: bool = True,
            post_process_graph: bool = True,
    ) -> BulkStartResponse:
        if self._publisher_for(operation) is None:
            raise BulkOperationUnavailableException(
                f"The '{operation.value}' operation is not available in this deployment."
            )

        existing = await self._store.get_snapshot(operation=operation)
        if existing is not None and existing.get("is_running"):
            raise BulkOperationConflictException(
                f"A '{operation.value}' bulk job is already running."
            )

        document_ids = await self._resolve_target_ids(selector)
        job_id = uuid.uuid4().hex
        total = len(document_ids)

        await self._store.begin_job(operation=operation, job_id=job_id, total=total)

        logger.info(
            "A bulk operation was accepted.",
            extra={
                "operation": operation.value,
                "job_id": job_id,
                "total": total,
                "user_id": user.id,
                "selector": "all" if selector.all_documents else "ids",
            },
        )

        if total == 0:
            # Nothing to enqueue: flip the freshly-created job to a terminal state.
            await self._store.mark(operation=operation, job_id=job_id)
            return BulkStartResponse(job_id=job_id, operation=operation, total=0, queued=False)

        op_kwargs = self._publish_kwargs(
            operation,
            force=force,
            prefer_docling=prefer_docling,
            post_process=post_process,
            post_process_graph=post_process_graph,
        )
        # Preserve the requester's bearer token in the detached task so downstream
        # providers authenticate as that user (the request context is gone by then).
        token = get_request_token()
        task = asyncio.create_task(
            self._fan_out(
                operation=operation,
                job_id=job_id,
                document_ids=document_ids,
                user=user,
                token=token,
                op_kwargs=op_kwargs,
            )
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

        return BulkStartResponse(job_id=job_id, operation=operation, total=total, queued=True)

    async def status(
            self,
            *,
            operation: BulkOperation,
    ) -> BulkJobStatusResponse:
        snapshot = await self._store.get_snapshot(operation=operation)
        return self._to_status_response(operation, snapshot)

    async def stop(
            self,
            *,
            operation: BulkOperation,
    ) -> BulkJobStatusResponse:
        await self._store.request_stop(operation=operation)
        logger.info("A bulk operation stop was requested.", extra={"operation": operation.value})
        snapshot = await self._store.get_snapshot(operation=operation)
        return self._to_status_response(operation, snapshot)

    async def _resolve_target_ids(self, selector: DocumentSelector) -> list[int]:
        if selector.document_ids is not None:
            return selector.document_ids[:MAX_POST_PROCESS_DOCUMENT_IDS]

        async with self._database_manager.session() as session:
            documents = await self._document_repository.get_documents(database_session=session)
        ids = [int(document.id) for document in documents]
        return ids[:MAX_POST_PROCESS_DOCUMENT_IDS]

    async def _fan_out(
            self,
            *,
            operation: BulkOperation,
            job_id: str,
            document_ids: list[int],
            user: AuthenticatedUser,
            token: Optional[str],
            op_kwargs: dict[str, Any],
    ) -> None:
        set_request_token(token)
        publisher = self._publisher_for(operation)
        assert publisher is not None  # guarded in start()

        for index, document_id in enumerate(document_ids):
            if await self._store.is_stopped(operation=operation, job_id=job_id):
                # Count the not-yet-enqueued remainder as processed so the job
                # converges to a terminal state instead of hanging.
                remaining = len(document_ids) - index
                if remaining > 0:
                    await self._store.mark(
                        operation=operation, job_id=job_id, processed_increment=remaining
                    )
                logger.info(
                    "Bulk fan-out stopped by request.",
                    extra={"operation": operation.value, "job_id": job_id, "remaining": remaining},
                )
                return

            try:
                await publisher.publish(  # type: ignore[call-arg]
                    document_id=document_id,
                    user=user,
                    batch_id=job_id,
                    **op_kwargs,
                )
            except Exception as exc:
                # The command never reached the queue, so no consumer will mark it;
                # account for it here to keep the job total consistent.
                await self._store.mark(operation=operation, job_id=job_id, failed_increment=1)
                await self._store.append_error(
                    operation=operation,
                    job_id=job_id,
                    error={
                        "document_id": document_id,
                        "error": f"publish failed: {exc}"[:MAX_POST_PROCESS_ERROR_MESSAGE_CHARS],
                    },
                )
                logger.warning(
                    "Failed to enqueue a bulk command.",
                    extra={"operation": operation.value, "job_id": job_id, "document_id": document_id},
                )

        logger.info(
            "Bulk fan-out finished enqueuing.",
            extra={"operation": operation.value, "job_id": job_id, "total": len(document_ids)},
        )

    def _publisher_for(self, operation: BulkOperation) -> Optional[object]:
        return {
            BulkOperation.reembed: self._reembed_publisher,
            BulkOperation.reprocess: self._reprocess_publisher,
            BulkOperation.enrich: self._enrichment_publisher,
            BulkOperation.graph_extract: self._graph_extraction_publisher,
        }[operation]

    @staticmethod
    def _publish_kwargs(
            operation: BulkOperation,
            *,
            force: bool,
            prefer_docling: bool,
            post_process: bool,
            post_process_graph: bool,
    ) -> dict[str, Any]:
        if operation is BulkOperation.reembed:
            return {"force": force}
        if operation is BulkOperation.reprocess:
            return {
                "prefer_docling": prefer_docling,
                "post_process": post_process,
                "post_process_graph": post_process_graph,
            }
        if operation is BulkOperation.graph_extract:
            return {"force": force}
        return {}

    @staticmethod
    def _to_status_response(
            operation: BulkOperation,
            snapshot: Optional[dict[str, Any]],
    ) -> BulkJobStatusResponse:
        if snapshot is None:
            return BulkJobStatusResponse(
                operation=operation,
                is_running=False,
                total=0,
                processed=0,
                failed=0,
            )

        raw_errors = snapshot.get("errors") or []
        errors = [
            BulkJobError(document_id=item.get("document_id"), error=str(item.get("error", "")))
            for item in raw_errors
            if isinstance(item, dict) and item.get("error")
        ]
        return BulkJobStatusResponse(
            job_id=snapshot.get("job_id"),
            operation=operation,
            is_running=bool(snapshot.get("is_running")),
            stop_requested=bool(snapshot.get("stop_requested")),
            total=int(snapshot.get("total", 0)),
            processed=int(snapshot.get("processed", 0)),
            failed=int(snapshot.get("failed", 0)),
            started_at=snapshot.get("started_at"),
            finished_at=snapshot.get("finished_at"),
            errors=errors,
        )
