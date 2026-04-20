import logging
import uuid
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.authorization.authorizer import Authorizer
from app.application.coordination.interfaces.post_process_job_progress_store_interface import (
    PostProcessJobProgressStoreInterface,
)
from app.application.services.document.post_process_document_service.exceptions.post_process_document_service_exception import (
    PostProcessAlreadyRunningException,
    PostProcessDocumentInvalidRequestException,
    PostProcessNotRunningException,
)
from app.application.services.document.post_process_document_service.interfaces.post_process_document_service_interface import (
    PostProcessDocumentServiceInterface,
)
from app.application.services.document.post_process_document_service.post_process_document_service_settings import (
    PostProcessDocumentServiceSettings,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document_processing_permissions import DocumentProcessingPermissions
from app.domain.dtos.document.post_process_document.post_process_document_error import PostProcessDocumentError
from app.domain.dtos.document.post_process_document.post_process_documents_request import PostProcessDocumentsRequest
from app.domain.dtos.document.post_process_document.post_process_documents_start_response import (
    PostProcessDocumentsStartResponse,
)
from app.domain.dtos.document.post_process_document.post_process_documents_status_response import (
    PostProcessDocumentsStatusResponse,
)
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.post_process_document_job_publisher_interface import (
    PostProcessDocumentJobPublisherInterface,
)
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_exception import RabbitMQPublishException
from app.infrastructure.persistence.database.database_manager.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface,
)
logger = logging.getLogger(__name__)


class PostProcessDocumentService(PostProcessDocumentServiceInterface):
    def __init__(
            self,
            database_manager: DatabaseManagerInterface,
            document_repository: DocumentRepositoryInterface,
            job_progress_store: PostProcessJobProgressStoreInterface,
            post_process_document_job_publisher: PostProcessDocumentJobPublisherInterface,
            authorizer: Authorizer,
            post_process_document_service_settings: Optional[PostProcessDocumentServiceSettings] = None,
    ) -> None:
        self._database_manager = database_manager
        self._document_repository = document_repository
        self._job_progress_store = job_progress_store
        self._job_publisher = post_process_document_job_publisher
        self._settings = post_process_document_service_settings or PostProcessDocumentServiceSettings()
        self._authorizer = authorizer

    async def start_all(
            self,
            authenticated_user: AuthenticatedUser,
    ) -> PostProcessDocumentsStartResponse:
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({DocumentProcessingPermissions.POST_PROCESS_DOCUMENTS_START_ALL}),
        )

        logger.info(
            "Starting post-processing for all documents that are missing metadata.",
            extra={"user_id": authenticated_user.id},
        )

        async with self._database_manager.session() as session:
            documents = await self._document_repository.get_documents_missing_metadata(
                database_session=session,
            )
            document_ids = [doc.id for doc in documents]

        if not document_ids:
            return PostProcessDocumentsStartResponse(
                message="No documents are missing metadata.",
                total_documents=0,
                job_id=None,
            )

        return await self._enqueue_document_job(
            document_ids=document_ids,
            authenticated_user=authenticated_user,
            message="Post-processing has started.",
        )

    async def start_for_documents(
            self,
            post_process_documents_request: PostProcessDocumentsRequest,
            authenticated_user: AuthenticatedUser,
    ) -> PostProcessDocumentsStartResponse:
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({DocumentProcessingPermissions.POST_PROCESS_DOCUMENTS_START}),
        )
        if len(post_process_documents_request.document_ids) > self._settings.max_document_ids:
            raise PostProcessDocumentInvalidRequestException(
                "The number of document identifiers exceeds the maximum allowed.",
            )

        document_ids = post_process_documents_request.document_ids

        logger.info(
            "Starting post-processing for the selected documents.",
            extra={"user_id": authenticated_user.id, "document_ids_count": len(document_ids)},
        )

        return await self._enqueue_document_job(
            document_ids=document_ids,
            authenticated_user=authenticated_user,
            message="Post-processing has started for the selected documents.",
        )

    async def get_status(
            self,
            authenticated_user: AuthenticatedUser,
    ) -> PostProcessDocumentsStatusResponse:
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({DocumentProcessingPermissions.POST_PROCESS_DOCUMENTS_STATUS}),
        )
        snapshot = await self._job_progress_store.get_document_job_snapshot()
        return self._document_status_from_snapshot(snapshot)

    async def stop(
            self,
            authenticated_user: AuthenticatedUser,
    ) -> None:
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({DocumentProcessingPermissions.POST_PROCESS_DOCUMENTS_STOP}),
        )
        snapshot = await self._job_progress_store.get_document_job_snapshot()
        if snapshot is None or not snapshot.get("is_running"):
            raise PostProcessNotRunningException("Post-processing is not running.")

        logger.info("A stop signal was sent for post-processing.")
        await self._job_progress_store.request_document_stop()

    async def _enqueue_document_job(
            self,
            document_ids: list[int],
            authenticated_user: AuthenticatedUser,
            message: str,
    ) -> PostProcessDocumentsStartResponse:
        job_id = uuid.uuid4().hex
        total = len(document_ids)
        begun = await self._job_progress_store.try_begin_document_job(
            job_id=job_id,
            total_documents=total,
            document_ids=document_ids,
            triggered_by=authenticated_user,
        )
        if not begun:
            raise PostProcessAlreadyRunningException("Post-processing is already running.")

        try:
            await self._job_publisher.publish_job(job_id)
        except Exception as e:
            await self._job_progress_store.abort_document_job(job_id)
            raise RabbitMQPublishException("Failed to enqueue the document post-processing job.") from e

        return PostProcessDocumentsStartResponse(
            message=message,
            total_documents=total,
            job_id=job_id,
        )

    def _document_status_from_snapshot(
            self,
            snapshot: Optional[dict],
    ) -> PostProcessDocumentsStatusResponse:
        if snapshot is None:
            return PostProcessDocumentsStatusResponse(
                is_running=False,
                total_documents=0,
                processed_documents=0,
                failed_documents=0,
                current_document_id=None,
                started_at=None,
                finished_at=None,
                errors=[],
                job_id=None,
            )

        errors_raw = snapshot.get("errors") or []
        errors: list[PostProcessDocumentError] = []
        for item in errors_raw:
            if isinstance(item, PostProcessDocumentError):
                errors.append(item)
            else:
                errors.append(PostProcessDocumentError.model_validate(item))

        started_at = self._parse_optional_datetime(snapshot.get("started_at"))
        finished_at = self._parse_optional_datetime(snapshot.get("finished_at"))

        return PostProcessDocumentsStatusResponse(
            is_running=bool(snapshot.get("is_running")),
            total_documents=int(snapshot.get("total_documents", 0)),
            processed_documents=int(snapshot.get("processed_documents", 0)),
            failed_documents=int(snapshot.get("failed_documents", 0)),
            current_document_id=snapshot.get("current_document_id"),
            started_at=started_at,
            finished_at=finished_at,
            errors=errors,
            job_id=snapshot.get("job_id"),
        )

    @staticmethod
    def _parse_optional_datetime(value: object) -> Optional[datetime]:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return None


async def get_post_process_document_service(
        request: Request,
) -> PostProcessDocumentServiceInterface:
    try:
        return request.app.state.post_process_document_service
    except AttributeError:
        logger.error("PostProcessDocumentService is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostProcessDocumentService is not registered on the application state.",
        )
