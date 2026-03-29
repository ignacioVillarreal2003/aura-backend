import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, Request, status

from app.application.services.document.post_process_document_service.exceptions.post_process_document_service_exception import (
    PostProcessAlreadyRunningException,
    PostProcessNotRunningException
)
from app.application.services.document.post_process_document_service.interfaces.post_process_document_service_interface import (
    PostProcessDocumentServiceInterface
)
from app.domain.dtos.document.post_process_document_controller.post_process_document_start_response import \
    PostProcessDocumentStartResponse
from app.domain.dtos.document.post_process_document_controller.post_process_document_status_response import (
    PostProcessDocumentError,
    PostProcessStatusResponse
)
from app.domain.models.authenticated_user import AuthenticatedUser
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
            llm_provider: LlmProviderInterface
    ) -> None:
        self._database_manager = database_manager
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._llm_provider = llm_provider

        self._task: Optional[asyncio.Task] = None
        self._stop_event: asyncio.Event = asyncio.Event()

        self._is_running: bool = False
        self._total_documents: int = 0
        self._processed_documents: int = 0
        self._failed_documents: int = 0
        self._current_document_id: Optional[int] = None
        self._started_at: Optional[datetime] = None
        self._finished_at: Optional[datetime] = None
        self._errors: List[PostProcessDocumentError] = []

    async def start_all(
            self,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessDocumentStartResponse:
        if self._is_running:
            raise PostProcessAlreadyRunningException(
                "Post-processing is already running"
            )

        logger.info("Starting post-processing for all documents missing metadata",
                     extra={"user_id": authenticated_user.id})

        async with self._database_manager.session() as session:
            documents = await self._document_repository.get_documents_missing_metadata(
                database_session=session
            )
            document_ids = [doc.id for doc in documents]

        if not document_ids:
            return PostProcessDocumentStartResponse(
                message="No documents found missing metadata",
                total_documents=0
            )

        self._launch_background_task(document_ids=document_ids, authenticated_user=authenticated_user)

        return PostProcessDocumentStartResponse(
            message="Post-processing started",
            total_documents=len(document_ids)
        )

    async def start_for_documents(
            self,
            document_ids: List[int],
            authenticated_user: AuthenticatedUser
    ) -> PostProcessDocumentStartResponse:
        if self._is_running:
            raise PostProcessAlreadyRunningException(
                "Post-processing is already running"
            )

        logger.info(
            "Starting post-processing for specific documents",
            extra={"user_id": authenticated_user.id, "document_ids": document_ids}
        )

        self._launch_background_task(document_ids=document_ids, authenticated_user=authenticated_user)

        return PostProcessDocumentStartResponse(
            message="Post-processing started for selected documents",
            total_documents=len(document_ids)
        )

    def get_status(self) -> PostProcessStatusResponse:
        return PostProcessStatusResponse(
            is_running=self._is_running,
            total_documents=self._total_documents,
            processed_documents=self._processed_documents,
            failed_documents=self._failed_documents,
            current_document_id=self._current_document_id,
            started_at=self._started_at,
            finished_at=self._finished_at,
            errors=list(self._errors)
        )

    async def stop(self) -> None:
        if not self._is_running:
            raise PostProcessNotRunningException(
                "Post-processing is not running"
            )

        logger.info("Stop signal sent for post-processing")
        self._stop_event.set()

    def _launch_background_task(
            self,
            document_ids: List[int],
            authenticated_user: AuthenticatedUser
    ) -> None:
        self._reset_progress(total=len(document_ids))
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._run_post_processing(document_ids=document_ids, authenticated_user=authenticated_user)
        )

    def _reset_progress(self, total: int) -> None:
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
            document_ids: List[int],
            authenticated_user: AuthenticatedUser
    ) -> None:
        logger.info(
            "Background post-processing started",
            extra={"total_documents": len(document_ids), "user_id": authenticated_user.id}
        )

        try:
            for document_id in document_ids:
                if self._stop_event.is_set():
                    logger.info("Post-processing stopped by user request")
                    break

                self._current_document_id = document_id

                try:
                    await self._process_single_document(
                        document_id=document_id,
                        authenticated_user=authenticated_user
                    )
                    self._processed_documents += 1
                    logger.info(
                        "Document post-processed successfully",
                        extra={
                            "document_id": document_id,
                            "progress": f"{self._processed_documents}/{self._total_documents}"
                        }
                    )

                except Exception as e:
                    self._failed_documents += 1
                    self._errors.append(
                        PostProcessDocumentError(
                            document_id=document_id,
                            error=str(e)
                        )
                    )
                    logger.error(
                        "Failed to post-process document",
                        extra={"document_id": document_id, "error": str(e)}
                    )

        except Exception as e:
            logger.exception(
                "Unexpected error in background post-processing",
                extra={"error": str(e)}
            )

        finally:
            self._is_running = False
            self._current_document_id = None
            self._finished_at = datetime.now(timezone.utc)

            logger.info(
                "Background post-processing finished",
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
                logger.warning("Document not found, skipping",
                               extra={"document_id": document_id})
                return

            fragments = await self._fragment_repository.get_fragments_by_document_id(
                document_id=document_id,
                database_session=session
            )

            if not fragments:
                logger.warning("No fragments found for document, skipping",
                               extra={"document_id": document_id})
                return

            content = "\n\n".join(
                fragment.content for fragment in fragments if fragment.content
            )

            if not content.strip():
                logger.warning("Document has no text content in fragments, skipping",
                               extra={"document_id": document_id})
                return

            classify_response = await self._llm_provider.classify_document(
                document_name=document.name,
                content=content,
                authenticated_user=authenticated_user
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


async def get_post_process_document_service(
        request: Request
) -> PostProcessDocumentServiceInterface:
    try:
        return request.app.state.post_process_document_service
    except AttributeError:
        logger.error("PostProcessDocumentService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostProcessDocumentService not configured"
        )
