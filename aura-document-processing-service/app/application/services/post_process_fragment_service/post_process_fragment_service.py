import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import select

from app.application.services.post_process_fragment_service.exceptions.post_process_fragment_service_exception import (
    PostProcessFragmentAlreadyRunningException,
    PostProcessFragmentNotRunningException
)
from app.application.services.post_process_fragment_service.interfaces.post_process_fragment_service_interface import (
    PostProcessFragmentServiceInterface
)
from app.domain.dtos.post_process_fragment_controller.post_process_fragment_start_response import (
    PostProcessFragmentStartResponse
)
from app.domain.dtos.post_process_fragment_controller.post_process_fragment_status_response import (
    PostProcessFragmentError,
    PostProcessFragmentStatusResponse
)
from app.domain.models.fragment import Fragment
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.llm_provider.interfaces.llm_provider_interface import LlmProviderInterface
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface
)
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)

logger = logging.getLogger(__name__)


class PostProcessFragmentService(PostProcessFragmentServiceInterface):
    def __init__(
            self,
            database_manager: DatabaseManagerInterface,
            fragment_repository: FragmentRepositoryInterface,
            llm_provider: LlmProviderInterface
    ) -> None:
        self._database_manager = database_manager
        self._fragment_repository = fragment_repository
        self._llm_provider = llm_provider

        self._task: Optional[asyncio.Task] = None
        self._stop_event: asyncio.Event = asyncio.Event()

        self._is_running: bool = False
        self._total_fragments: int = 0
        self._processed_fragments: int = 0
        self._failed_fragments: int = 0
        self._current_fragment_id: Optional[int] = None
        self._started_at: Optional[datetime] = None
        self._finished_at: Optional[datetime] = None
        self._errors: List[PostProcessFragmentError] = []

    async def start_all(
            self,
            authenticated_user: AuthenticationResponse
    ) -> PostProcessFragmentStartResponse:
        if self._is_running:
            raise PostProcessFragmentAlreadyRunningException(
                "Fragment post-processing is already running"
            )

        logger.info(
            "Starting fragment post-processing for all fragments missing metadata",
            extra={"user_id": authenticated_user.id}
        )

        async with self._database_manager.session() as session:
            fragments = await self._fragment_repository.get_fragments_missing_metadata(
                database_session=session
            )
            fragment_ids = [f.id for f in fragments]

        if not fragment_ids:
            return PostProcessFragmentStartResponse(
                message="No fragments found missing metadata",
                total_fragments=0
            )

        self._launch_background_task(fragment_ids=fragment_ids, authenticated_user=authenticated_user)

        return PostProcessFragmentStartResponse(
            message="Fragment post-processing started",
            total_fragments=len(fragment_ids)
        )

    async def start_for_documents(
            self,
            document_ids: List[int],
            authenticated_user: AuthenticationResponse
    ) -> PostProcessFragmentStartResponse:
        if self._is_running:
            raise PostProcessFragmentAlreadyRunningException(
                "Fragment post-processing is already running"
            )

        logger.info(
            "Starting fragment post-processing for specific documents",
            extra={"user_id": authenticated_user.id, "document_ids": document_ids}
        )

        async with self._database_manager.session() as session:
            fragments = await self._fragment_repository.get_fragments_missing_metadata_by_document_ids(
                document_ids=document_ids,
                database_session=session
            )
            fragment_ids = [f.id for f in fragments]

        if not fragment_ids:
            return PostProcessFragmentStartResponse(
                message="No fragments found missing metadata for the given documents",
                total_fragments=0
            )

        self._launch_background_task(fragment_ids=fragment_ids, authenticated_user=authenticated_user)

        return PostProcessFragmentStartResponse(
            message="Fragment post-processing started for selected documents",
            total_fragments=len(fragment_ids)
        )

    def get_status(self) -> PostProcessFragmentStatusResponse:
        return PostProcessFragmentStatusResponse(
            is_running=self._is_running,
            total_fragments=self._total_fragments,
            processed_fragments=self._processed_fragments,
            failed_fragments=self._failed_fragments,
            current_fragment_id=self._current_fragment_id,
            started_at=self._started_at,
            finished_at=self._finished_at,
            errors=list(self._errors)
        )

    async def stop(self) -> None:
        if not self._is_running:
            raise PostProcessFragmentNotRunningException(
                "Fragment post-processing is not running"
            )

        logger.info("Stop signal sent for fragment post-processing")
        self._stop_event.set()

    def _launch_background_task(
            self,
            fragment_ids: List[int],
            authenticated_user: AuthenticationResponse
    ) -> None:
        self._reset_progress(total=len(fragment_ids))
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._run_post_processing(fragment_ids=fragment_ids, authenticated_user=authenticated_user)
        )

    def _reset_progress(self, total: int) -> None:
        self._is_running = True
        self._total_fragments = total
        self._processed_fragments = 0
        self._failed_fragments = 0
        self._current_fragment_id = None
        self._started_at = datetime.now(timezone.utc)
        self._finished_at = None
        self._errors = []

    async def _run_post_processing(
            self,
            fragment_ids: List[int],
            authenticated_user: AuthenticationResponse
    ) -> None:
        logger.info(
            "Background fragment post-processing started",
            extra={"total_fragments": len(fragment_ids), "user_id": authenticated_user.id}
        )

        try:
            for fragment_id in fragment_ids:
                if self._stop_event.is_set():
                    logger.info("Fragment post-processing stopped by user request")
                    break

                self._current_fragment_id = fragment_id

                try:
                    await self._process_single_fragment(
                        fragment_id=fragment_id,
                        authenticated_user=authenticated_user
                    )
                    self._processed_fragments += 1
                    logger.info(
                        "Fragment post-processed successfully",
                        extra={
                            "fragment_id": fragment_id,
                            "progress": f"{self._processed_fragments}/{self._total_fragments}"
                        }
                    )

                except Exception as e:
                    self._failed_fragments += 1
                    self._errors.append(
                        PostProcessFragmentError(
                            fragment_id=fragment_id,
                            error=str(e)
                        )
                    )
                    logger.error(
                        "Failed to post-process fragment",
                        extra={"fragment_id": fragment_id, "error": str(e)}
                    )

        except Exception as e:
            logger.exception(
                "Unexpected error in background fragment post-processing",
                extra={"error": str(e)}
            )

        finally:
            self._is_running = False
            self._current_fragment_id = None
            self._finished_at = datetime.now(timezone.utc)

            logger.info(
                "Background fragment post-processing finished",
                extra={
                    "processed": self._processed_fragments,
                    "failed": self._failed_fragments,
                    "total": self._total_fragments
                }
            )

    async def _process_single_fragment(
            self,
            fragment_id: int,
            authenticated_user: AuthenticationResponse
    ) -> None:
        async with self._database_manager.session() as session:
            result = await session.execute(
                select(Fragment).where(Fragment.id == fragment_id)
            )
            fragment = result.scalars().first()

            if fragment is None:
                logger.warning(
                    "Fragment not found, skipping",
                    extra={"fragment_id": fragment_id}
                )
                return

            if not fragment.content or not fragment.content.strip():
                logger.warning(
                    "Fragment has no text content, skipping",
                    extra={"fragment_id": fragment_id}
                )
                return

            enrich_response = await self._llm_provider.enrich_fragment(
                content=fragment.content,
                authenticated_user=authenticated_user
            )

            fragment.summary = enrich_response.summary
            fragment.entities = enrich_response.entities
            fragment.topics = enrich_response.topics
            fragment.updated_by = authenticated_user.id
            fragment.updated_at = datetime.now(timezone.utc)

            await self._fragment_repository.update_fragment(
                fragment=fragment,
                database_session=session
            )


async def get_post_process_fragment_service(
        request: Request
) -> PostProcessFragmentServiceInterface:
    try:
        return request.app.state.post_process_fragment_service
    except AttributeError:
        logger.error("PostProcessFragmentService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostProcessFragmentService not configured"
        )
