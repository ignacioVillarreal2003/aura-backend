import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.fragment.post_process_fragment_service.exceptions.post_process_fragment_service_exception import (
    PostProcessFragmentAlreadyRunningException,
    PostProcessFragmentNotRunningException
)
from app.application.services.fragment.post_process_fragment_service.interfaces.post_process_fragment_service_interface import (
    PostProcessFragmentServiceInterface
)
from app.application.services.fragment.post_process_fragment_service.post_process_fragment_service_authorizer import (
    PostProcessFragmentServiceAuthorizer,
)
from app.application.services.fragment.post_process_fragment_service.post_process_fragment_service_settings import (
    PostProcessFragmentServiceSettings
)
from app.application.services.fragment.post_process_fragment_service.post_process_fragment_service_validator import (
    PostProcessFragmentServiceValidator,
)
from app.domain.dtos.fragment.post_process_fragment.post_process_fragments_request import (
    PostProcessFragmentsRequest
)
from app.domain.dtos.fragment.post_process_fragment.post_process_fragments_start_response import (
    PostProcessFragmentsStartResponse
)
from app.domain.dtos.fragment.post_process_fragment.post_process_fragments_status_response import (
    PostProcessFragmentError,
    PostProcessFragmentsStatusResponse
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.user.user_roles import ADMIN_ROLES
from app.domain.models.fragment import Fragment
from app.infrastructure.http.llm_provider.interfaces.llm_provider_interface import LlmProviderInterface
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
            llm_provider: LlmProviderInterface,
            post_process_fragment_service_settings: Optional[PostProcessFragmentServiceSettings] = None
    ) -> None:
        self._database_manager = database_manager
        self._fragment_repository = fragment_repository
        self._llm_provider = llm_provider
        self._settings = post_process_fragment_service_settings or PostProcessFragmentServiceSettings()
        self._authorizer = PostProcessFragmentServiceAuthorizer()
        self._validator = PostProcessFragmentServiceValidator(
            post_process_fragment_service_settings=self._settings
        )

        self._task: Optional[asyncio.Task] = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._lifecycle_lock: asyncio.Lock = asyncio.Lock()

        self._is_running: bool = False
        self._total_fragments: int = 0
        self._processed_fragments: int = 0
        self._failed_fragments: int = 0
        self._current_fragment_id: Optional[int] = None
        self._started_at: Optional[datetime] = None
        self._finished_at: Optional[datetime] = None
        self._errors: List[PostProcessFragmentError] = []
        self._errors_truncated: bool = False

    async def start_all(
            self,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessFragmentsStartResponse:
        self._authorizer.require_permissions(authenticated_user)
        self._authorizer.require_roles(
            authenticated_user=authenticated_user,
            allowed_roles=ADMIN_ROLES
        )

        async with self._lifecycle_lock:
            self._ensure_not_running()
            self._reset_progress(total=0)

        logger.info(
            "Starting fragment post-processing for all fragments that are missing metadata.",
            extra={
                "user_id": authenticated_user.id
            }
        )

        try:
            async with self._database_manager.session() as session:
                total = await self._fragment_repository.count_fragments_missing_metadata(
                    database_session=session
                )
        except Exception:
            await self._mark_not_running_after_setup_failure()
            raise

        if total == 0:
            await self._mark_not_running_no_work()
            return PostProcessFragmentsStartResponse(
                message="No fragments are missing metadata.",
                total_fragments=0
            )

        self._launch_background_task(
            total=total,
            authenticated_user=authenticated_user,
            document_ids=None
        )

        return PostProcessFragmentsStartResponse(
            message="Fragment post-processing has started.",
            total_fragments=total
        )

    async def start_for_documents(
            self,
            post_process_fragments_request: PostProcessFragmentsRequest,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessFragmentsStartResponse:
        self._authorizer.require_permissions(authenticated_user)
        self._authorizer.require_roles(
            authenticated_user=authenticated_user,
            allowed_roles=ADMIN_ROLES
        )
        self._validator.validate_post_process_fragments_request(post_process_fragments_request)

        document_ids = post_process_fragments_request.document_ids

        async with self._lifecycle_lock:
            self._ensure_not_running()
            self._reset_progress(total=0)

        logger.info(
            "Starting fragment post-processing for specific documents.",
            extra={
                "user_id": authenticated_user.id,
                "document_ids": document_ids
            }
        )

        try:
            async with self._database_manager.session() as session:
                total = await self._fragment_repository.count_fragments_missing_metadata_by_document_ids(
                    document_ids=document_ids,
                    database_session=session
                )
        except Exception:
            await self._mark_not_running_after_setup_failure()
            raise

        if total == 0:
            await self._mark_not_running_no_work()
            return PostProcessFragmentsStartResponse(
                message="No fragments are missing metadata for the given documents.",
                total_fragments=0
            )

        self._launch_background_task(
            total=total,
            authenticated_user=authenticated_user,
            document_ids=document_ids
        )

        return PostProcessFragmentsStartResponse(
            message="Fragment post-processing has started for the selected documents.",
            total_fragments=total
        )

    def get_status(
            self
    ) -> PostProcessFragmentsStatusResponse:
        return PostProcessFragmentsStatusResponse(
            is_running=self._is_running,
            total_fragments=self._total_fragments,
            processed_fragments=self._processed_fragments,
            failed_fragments=self._failed_fragments,
            current_fragment_id=self._current_fragment_id,
            started_at=self._started_at,
            finished_at=self._finished_at,
            errors=list(self._errors)
        )

    async def stop(
            self
    ) -> None:
        async with self._lifecycle_lock:
            if not self._is_running:
                raise PostProcessFragmentNotRunningException("Fragment post-processing is not running.")

        logger.info("A stop signal was sent for fragment post-processing.")
        self._stop_event.set()

    def _launch_background_task(
            self,
            total: int,
            authenticated_user: AuthenticatedUser,
            document_ids: Optional[List[int]] = None
    ) -> None:
        self._total_fragments = total
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._run_post_processing(
                authenticated_user=authenticated_user,
                document_ids=document_ids
            )
        )

    def _reset_progress(
            self,
            total: int
    ) -> None:
        self._is_running = True
        self._total_fragments = total
        self._processed_fragments = 0
        self._failed_fragments = 0
        self._current_fragment_id = None
        self._started_at = datetime.now(timezone.utc)
        self._finished_at = None
        self._errors = []
        self._errors_truncated = False

    async def _run_post_processing(
            self,
            authenticated_user: AuthenticatedUser,
            document_ids: Optional[List[int]] = None
    ) -> None:
        logger.info(
            "Background fragment post-processing has started.",
            extra={
                "total_fragments": self._total_fragments,
                "user_id": authenticated_user.id,
                "document_ids": document_ids,
                "batch_size": self._settings.batch_size
            }
        )

        last_fragment_id: Optional[int] = None

        try:
            while not self._stop_event.is_set():
                if (self._processed_fragments + self._failed_fragments) >= self._total_fragments:
                    break

                async with self._database_manager.session() as session:
                    if document_ids is None:
                        fragment_ids = await self._fragment_repository.get_fragment_ids_missing_metadata(
                            database_session=session,
                            limit=self._settings.batch_size,
                            last_fragment_id=last_fragment_id
                        )
                    else:
                        fragment_ids = await self._fragment_repository.get_fragment_ids_missing_metadata_by_document_ids(
                            document_ids=document_ids,
                            database_session=session,
                            limit=self._settings.batch_size,
                            last_fragment_id=last_fragment_id
                        )

                    if not fragment_ids:
                        break

                    last_fragment_id = fragment_ids[-1]

                    for fragment_id in fragment_ids:
                        if self._stop_event.is_set():
                            logger.info("Fragment post-processing was stopped by user request.")
                            break
                        if (self._processed_fragments + self._failed_fragments) >= self._total_fragments:
                            break

                        self._current_fragment_id = fragment_id

                        try:
                            await self._process_single_fragment(
                                fragment_id=fragment_id,
                                authenticated_user=authenticated_user,
                                database_session=session
                            )
                            self._processed_fragments += 1
                            logger.info(
                                "The fragment was post-processed successfully.",
                                extra={
                                    "fragment_id": fragment_id,
                                    "progress": f"{self._processed_fragments}/{self._total_fragments}"
                                }
                            )
                        except Exception as e:
                            self._failed_fragments += 1
                            self._append_error(fragment_id=fragment_id, error=type(e).__name__)
                            logger.error(
                                "Failed to post-process the fragment.",
                                extra={
                                    "fragment_id": fragment_id,
                                    "exception_type": type(e).__name__
                                }
                            )

                if self._stop_event.is_set():
                    break

        except Exception as e:
            logger.exception(
                "An unexpected error occurred in background fragment post-processing.",
                extra={
                    "exception_type": type(e).__name__
                }
            )

        finally:
            async with self._lifecycle_lock:
                self._is_running = False
                self._current_fragment_id = None
                self._finished_at = datetime.now(timezone.utc)

            logger.info(
                "Background fragment post-processing has finished.",
                extra={
                    "processed": self._processed_fragments,
                    "failed": self._failed_fragments,
                    "total": self._total_fragments
                }
            )

    async def _process_single_fragment(
            self,
            fragment_id: int,
            authenticated_user: AuthenticatedUser,
            database_session: AsyncSession
    ) -> None:
        result = await database_session.execute(
            select(Fragment).where(Fragment.id == fragment_id)
        )
        fragment = result.scalars().first()

        if fragment is None:
            logger.warning(
                "The fragment was not found; skipping it.",
                extra={
                    "fragment_id": fragment_id
                }
            )
            return

        if not fragment.content or not fragment.content.strip():
            logger.warning(
                "The fragment has no text content; skipping it.",
                extra={
                    "fragment_id": fragment_id
                }
            )
            return

        try:
            enrich_response = await asyncio.wait_for(
                self._llm_provider.enrich_fragment(
                    content=fragment.content,
                    authenticated_user=authenticated_user
                ),
                timeout=self._settings.llm_timeout_seconds
            )
        except TimeoutError as e:
            raise TimeoutError("The LLM enrichment step timed out.") from e

        fragment.summary = enrich_response.summary
        fragment.entities = enrich_response.entities
        fragment.topics = enrich_response.topics
        fragment.updated_by = authenticated_user.id
        fragment.updated_at = datetime.now(timezone.utc)

        await self._fragment_repository.update_fragment(
            fragment=fragment,
            database_session=database_session
        )

    def _append_error(
            self,
            fragment_id: int,
            error: str
    ) -> None:
        if len(self._errors) < self._settings.max_errors_in_status:
            self._errors.append(
                PostProcessFragmentError(
                    fragment_id=fragment_id,
                    error=error
                )
            )
            return

        if not self._errors_truncated:
            logger.warning(
                "The error list reached the maximum length; further errors will be omitted.",
                extra={
                    "max_errors_in_status": self._settings.max_errors_in_status
                }
            )
            self._errors_truncated = True

    def _ensure_not_running(
            self
    ) -> None:
        if self._is_running:
            raise PostProcessFragmentAlreadyRunningException("Fragment post-processing is already running.")

    async def _mark_not_running_after_setup_failure(
            self
    ) -> None:
        async with self._lifecycle_lock:
            self._is_running = False
            self._finished_at = datetime.now(timezone.utc)

    async def _mark_not_running_no_work(
            self
    ) -> None:
        async with self._lifecycle_lock:
            self._is_running = False
            self._finished_at = datetime.now(timezone.utc)


async def get_post_process_fragment_service(
        request: Request
) -> PostProcessFragmentServiceInterface:
    try:
        return request.app.state.post_process_fragment_service
    except AttributeError:
        logger.error("PostProcessFragmentService is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostProcessFragmentService is not registered on the application state."
        )
