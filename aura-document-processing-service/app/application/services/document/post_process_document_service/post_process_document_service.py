import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.authorization.base_service_authorizer import BaseServiceAuthorizer
from app.application.services.document.post_process_document_service.exceptions.post_process_document_service_exception import (
    PostProcessAlreadyRunningException,
    PostProcessDocumentInvalidRequestException,
    PostProcessDocumentUnauthorizedException,
    PostProcessNotRunningException,
)
from app.application.services.document.post_process_document_service.interfaces.post_process_document_service_interface import (
    PostProcessDocumentServiceInterface
)
from app.application.services.document.post_process_document_service.post_process_document_service_settings import (
    PostProcessDocumentServiceSettings
)
from app.domain.dtos.document.post_process_document.post_process_documents_request import (
    PostProcessDocumentsRequest
)
from app.domain.dtos.document.post_process_document.post_process_documents_start_response import (
    PostProcessDocumentsStartResponse
)
from app.domain.dtos.document.post_process_document.post_process_documents_status_response import (
    PostProcessDocumentError,
    PostProcessDocumentsStatusResponse
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.user.user_roles import ADMIN_ROLES
from app.infrastructure.http.llm_provider.interfaces.llm_provider_interface import LlmProviderInterface
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface
)
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)

logger = logging.getLogger(__name__)


class PostProcessDocumentService(PostProcessDocumentServiceInterface):
    def __init__(
            self,
            database_manager: DatabaseManagerInterface,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            llm_provider: LlmProviderInterface,
            post_process_document_service_settings: Optional[PostProcessDocumentServiceSettings] = None
    ) -> None:
        self._database_manager = database_manager
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._llm_provider = llm_provider
        self._settings = post_process_document_service_settings or PostProcessDocumentServiceSettings()

        self._authorizer = BaseServiceAuthorizer(
            unauthorized_exception_class=PostProcessDocumentUnauthorizedException,
            required_permissions=self._settings.REQUIRED_PERMISSIONS,
            operation_label="document post-processing",
        )

        self._task: Optional[asyncio.Task] = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._lifecycle_lock = asyncio.Lock()

        self._is_running: bool = False
        self._total_documents: int = 0
        self._processed_documents: int = 0
        self._failed_documents: int = 0
        self._current_document_id: Optional[int] = None
        self._started_at: Optional[datetime] = None
        self._finished_at: Optional[datetime] = None
        self._errors: list[PostProcessDocumentError] = []

    async def start_all(
            self,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessDocumentsStartResponse:
        self._authorizer.require_permissions(authenticated_user)
        self._authorizer.require_roles(
            authenticated_user=authenticated_user,
            allowed_roles=ADMIN_ROLES
        )

        async with self._lifecycle_lock:
            if self._is_running:
                raise PostProcessAlreadyRunningException("Post-processing is already running.")

            logger.info(
                "Starting post-processing for all documents that are missing metadata.",
                extra={
                    "user_id": authenticated_user.id
                }
            )

            async with self._database_manager.session() as session:
                documents = await self._document_repository.get_documents_missing_metadata(
                    database_session=session
                )
                document_ids = [doc.id for doc in documents]

            if not document_ids:
                return PostProcessDocumentsStartResponse(
                    message="No documents are missing metadata.",
                    total_documents=0
                )

            self._launch_background_task(
                document_ids=document_ids,
                authenticated_user=authenticated_user
            )

            return PostProcessDocumentsStartResponse(
                message="Post-processing has started.",
                total_documents=len(document_ids)
            )

    async def start_for_documents(
            self,
            post_process_documents_request: PostProcessDocumentsRequest,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessDocumentsStartResponse:
        self._authorizer.require_permissions(authenticated_user)
        self._authorizer.require_roles(
            authenticated_user=authenticated_user,
            allowed_roles=ADMIN_ROLES
        )
        if len(post_process_documents_request.document_ids) > self._settings.max_document_ids:
            raise PostProcessDocumentInvalidRequestException(
                "The number of document identifiers exceeds the maximum allowed."
            )
        document_ids = post_process_documents_request.document_ids

        async with self._lifecycle_lock:
            if self._is_running:
                raise PostProcessAlreadyRunningException("Post-processing is already running.")

            logger.info(
                "Starting post-processing for the selected documents.",
                extra={
                    "user_id": authenticated_user.id,
                    "document_ids_count": len(document_ids)
                }
            )

            self._launch_background_task(
                document_ids=document_ids,
                authenticated_user=authenticated_user
            )

            return PostProcessDocumentsStartResponse(
                message="Post-processing has started for the selected documents.",
                total_documents=len(document_ids)
            )

    def get_status(
            self
    ) -> PostProcessDocumentsStatusResponse:
        return PostProcessDocumentsStatusResponse(
            is_running=self._is_running,
            total_documents=self._total_documents,
            processed_documents=self._processed_documents,
            failed_documents=self._failed_documents,
            current_document_id=self._current_document_id,
            started_at=self._started_at,
            finished_at=self._finished_at,
            errors=list(self._errors)
        )

    async def stop(
            self
    ) -> None:
        async with self._lifecycle_lock:
            if not self._is_running:
                raise PostProcessNotRunningException("Post-processing is not running.")

            logger.info("A stop signal was sent for post-processing.")
            self._stop_event.set()

    def _launch_background_task(
            self,
            document_ids: list[int],
            authenticated_user: AuthenticatedUser
    ) -> None:
        self._reset_progress(total=len(document_ids))
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._run_post_processing(document_ids=document_ids, authenticated_user=authenticated_user)
        )

    def _reset_progress(
            self,
            total: int
    ) -> None:
        self._is_running = True
        self._total_documents = total
        self._processed_documents = 0
        self._failed_documents = 0
        self._current_document_id = None
        self._started_at = datetime.now(timezone.utc)
        self._finished_at = None
        self._errors = []

    async def _run_post_processing(
            self,
            document_ids: list[int],
            authenticated_user: AuthenticatedUser
    ) -> None:
        logger.info(
            "Background post-processing has started.",
            extra={
                "total_documents": len(document_ids),
                "user_id": authenticated_user.id
            }
        )

        try:
            for document_id in document_ids:
                if self._stop_event.is_set():
                    logger.info("Post-processing was stopped by user request.")
                    break

                self._current_document_id = document_id

                try:
                    await self._process_single_document(
                        document_id=document_id,
                        authenticated_user=authenticated_user
                    )
                    self._processed_documents += 1
                    logger.info(
                        "The document was post-processed successfully.",
                        extra={
                            "document_id": document_id,
                            "progress": f"{self._processed_documents}/{self._total_documents}"
                        }
                    )

                except Exception as e:
                    self._failed_documents += 1
                    self._append_error(document_id=document_id, error=type(e).__name__)
                    logger.error(
                        "Failed to post-process the document.",
                        extra={
                            "document_id": document_id,
                            "exception_type": type(e).__name__
                        }
                    )

        except Exception as e:
            logger.exception(
                "An unexpected error occurred in background post-processing.",
                extra={
                    "exception_type": type(e).__name__
                }
            )

        finally:
            async with self._lifecycle_lock:
                self._is_running = False
                self._current_document_id = None
                self._finished_at = datetime.now(timezone.utc)

            logger.info(
                "Background post-processing has finished.",
                extra={
                    "processed": self._processed_documents,
                    "failed": self._failed_documents,
                    "total": self._total_documents
                }
            )

    async def _process_single_document(
            self,
            document_id: int,
            authenticated_user: AuthenticatedUser
    ) -> None:
        async with self._database_manager.session() as session:
            document = await self._document_repository.get_document_by_id(
                document_id=document_id,
                database_session=session
            )

            if document is None:
                logger.warning(
                    "The document was not found; skipping it.",
                    extra={
                        "document_id": document_id
                    }
                )
                return

            fragments = await self._fragment_repository.get_fragments_by_document_id(
                document_id=document_id,
                database_session=session
            )

            if not fragments:
                logger.warning(
                    "No fragments were found for the document; skipping it.",
                    extra={
                        "document_id": document_id
                    }
                )
                return

            content = "\n\n".join(
                fragment.content for fragment in fragments if fragment.content
            )

            if not content.strip():
                logger.warning(
                    "The document has no text content in its fragments; skipping it.",
                    extra={
                        "document_id": document_id
                    }
                )
                return

            classify_response = await asyncio.wait_for(
                self._llm_provider.classify_document(
                    document_name=document.name,
                    content=content,
                    authenticated_user=authenticated_user
                ),
                timeout=self._settings.llm_timeout_seconds
            )

            document.type = classify_response.type
            document.category = classify_response.category
            document.description = classify_response.description
            document.updated_by = authenticated_user.id
            document.updated_at = datetime.now(timezone.utc)

            await self._document_repository.update_document(
                document=document,
                database_session=session
            )

    def _append_error(
            self,
            document_id: int,
            error: str
    ) -> None:
        if len(self._errors) >= self._settings.max_errors_in_status:
            return
        self._errors.append(
            PostProcessDocumentError(
                document_id=document_id,
                error=error
            )
        )


async def get_post_process_document_service(
        request: Request
) -> PostProcessDocumentServiceInterface:
    try:
        return request.app.state.post_process_document_service
    except AttributeError:
        logger.error("PostProcessDocumentService is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostProcessDocumentService is not registered on the application state."
        )
