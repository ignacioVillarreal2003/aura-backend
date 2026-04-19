import logging
import uuid
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.authorization.authorizer import Authorizer
from app.application.coordination.interfaces.post_process_job_progress_store_interface import (
    PostProcessJobProgressStoreInterface,
)
from app.application.services.fragment.post_process_fragment_service.exceptions.post_process_fragment_service_exception import (
    PostProcessFragmentAlreadyRunningException,
    PostProcessFragmentInvalidRequestException,
    PostProcessFragmentNotRunningException,
)
from app.application.services.fragment.post_process_fragment_service.interfaces.post_process_fragment_service_interface import (
    PostProcessFragmentServiceInterface,
)
from app.application.services.fragment.post_process_fragment_service.post_process_fragment_service_settings import (
    PostProcessFragmentServiceSettings,
)
from app.configuration.prometheus_post_process_metrics import post_process_jobs_published
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document_processing_permissions import DocumentProcessingPermissions
from app.domain.dtos.fragment.post_process_fragment.post_process_fragments_request import PostProcessFragmentsRequest
from app.domain.dtos.fragment.post_process_fragment.post_process_fragments_start_response import (
    PostProcessFragmentsStartResponse,
)
from app.domain.dtos.fragment.post_process_fragment.post_process_fragments_status_response import (
    PostProcessFragmentError,
    PostProcessFragmentsStatusResponse,
)
from app.infrastructure.messaging.rabbitmq.dtos.commands.post_process_fragment_job_command import (
    PostProcessFragmentJobCommand,
)
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.exceptions.rabbitmq_manager_exception import RabbitMQPublishException
from app.infrastructure.messaging.rabbitmq.interfaces.rabbitmq_manager_interface import RabbitMQManagerInterface
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface,
)

logger = logging.getLogger(__name__)


class PostProcessFragmentService(PostProcessFragmentServiceInterface):
    def __init__(
            self,
            database_manager: DatabaseManagerInterface,
            fragment_repository: FragmentRepositoryInterface,
            rabbitmq_manager: RabbitMQManagerInterface,
            job_progress_store: PostProcessJobProgressStoreInterface,
            authorizer: Authorizer,
            post_process_fragment_service_settings: Optional[PostProcessFragmentServiceSettings] = None,
    ) -> None:
        self._database_manager = database_manager
        self._fragment_repository = fragment_repository
        self._rabbitmq_manager = rabbitmq_manager
        self._job_progress_store = job_progress_store
        self._settings = post_process_fragment_service_settings or PostProcessFragmentServiceSettings()
        self._authorizer = authorizer

    async def start_all(
            self,
            authenticated_user: AuthenticatedUser,
    ) -> PostProcessFragmentsStartResponse:
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({DocumentProcessingPermissions.POST_PROCESS_FRAGMENTS_START_ALL}),
        )

        logger.info(
            "Starting fragment post-processing for all fragments that are missing metadata.",
            extra={"user_id": authenticated_user.id},
        )

        async with self._database_manager.session() as session:
            total = await self._fragment_repository.count_fragments_missing_metadata(
                database_session=session,
            )

        if total == 0:
            return PostProcessFragmentsStartResponse(
                message="No fragments are missing metadata.",
                total_fragments=0,
                job_id=None,
            )

        return await self._enqueue_fragment_job(
            total_fragments=total,
            document_ids=None,
            authenticated_user=authenticated_user,
            message="Fragment post-processing has started.",
        )

    async def start_for_documents(
            self,
            post_process_fragments_request: PostProcessFragmentsRequest,
            authenticated_user: AuthenticatedUser,
    ) -> PostProcessFragmentsStartResponse:
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({DocumentProcessingPermissions.POST_PROCESS_FRAGMENTS_START}),
        )
        if len(post_process_fragments_request.document_ids) > self._settings.max_document_ids:
            raise PostProcessFragmentInvalidRequestException(
                "The number of document identifiers exceeds the configured limit.",
            )

        document_ids = post_process_fragments_request.document_ids

        logger.info(
            "Starting fragment post-processing for specific documents.",
            extra={"user_id": authenticated_user.id, "document_ids": document_ids},
        )

        async with self._database_manager.session() as session:
            total = await self._fragment_repository.count_fragments_missing_metadata_by_document_ids(
                document_ids=document_ids,
                database_session=session,
            )

        if total == 0:
            return PostProcessFragmentsStartResponse(
                message="No fragments are missing metadata for the given documents.",
                total_fragments=0,
                job_id=None,
            )

        return await self._enqueue_fragment_job(
            total_fragments=total,
            document_ids=document_ids,
            authenticated_user=authenticated_user,
            message="Fragment post-processing has started for the selected documents.",
        )

    async def get_status(
            self,
            authenticated_user: AuthenticatedUser,
    ) -> PostProcessFragmentsStatusResponse:
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({DocumentProcessingPermissions.POST_PROCESS_FRAGMENTS_STATUS}),
        )
        snapshot = await self._job_progress_store.get_fragment_job_snapshot()
        return self._fragment_status_from_snapshot(snapshot)

    async def stop(
            self,
            authenticated_user: AuthenticatedUser,
    ) -> None:
        self._authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({DocumentProcessingPermissions.POST_PROCESS_FRAGMENTS_STOP}),
        )
        snapshot = await self._job_progress_store.get_fragment_job_snapshot()
        if snapshot is None or not snapshot.get("is_running"):
            raise PostProcessFragmentNotRunningException("Fragment post-processing is not running.")

        logger.info("A stop signal was sent for fragment post-processing.")
        await self._job_progress_store.request_fragment_stop()

    async def _enqueue_fragment_job(
            self,
            total_fragments: int,
            document_ids: Optional[list[int]],
            authenticated_user: AuthenticatedUser,
            message: str,
    ) -> PostProcessFragmentsStartResponse:
        job_id = uuid.uuid4().hex
        begun = await self._job_progress_store.try_begin_fragment_job(job_id=job_id, total_fragments=total_fragments)
        if not begun:
            raise PostProcessFragmentAlreadyRunningException("Fragment post-processing is already running.")

        command = PostProcessFragmentJobCommand(
            job_id=job_id,
            document_ids=document_ids,
            total_fragments=total_fragments,
            user_id=authenticated_user.id,
            user_email=authenticated_user.email,
            roles=list(authenticated_user.roles),
            permissions=list(authenticated_user.permissions),
        )
        envelope = MessageEnvelope.wrap(command)
        try:
            await self._rabbitmq_manager.publish(
                routing_key=self._rabbitmq_manager.settings.post_process_fragment_queue,
                body=envelope.to_bytes(),
                headers={"message_id": envelope.message_id},
            )
        except Exception as e:
            await self._job_progress_store.abort_fragment_job(job_id)
            raise RabbitMQPublishException("Failed to enqueue the fragment post-processing job.") from e

        post_process_jobs_published.labels("fragment").inc()
        return PostProcessFragmentsStartResponse(
            message=message,
            total_fragments=total_fragments,
            job_id=job_id,
        )

    def _fragment_status_from_snapshot(
            self,
            snapshot: Optional[dict],
    ) -> PostProcessFragmentsStatusResponse:
        if snapshot is None:
            return PostProcessFragmentsStatusResponse(
                is_running=False,
                total_fragments=0,
                processed_fragments=0,
                failed_fragments=0,
                current_fragment_id=None,
                started_at=None,
                finished_at=None,
                errors=[],
                job_id=None,
            )

        errors_raw = snapshot.get("errors") or []
        errors: list[PostProcessFragmentError] = []
        for item in errors_raw:
            if isinstance(item, PostProcessFragmentError):
                errors.append(item)
            else:
                errors.append(PostProcessFragmentError.model_validate(item))

        started_at = self._parse_optional_datetime(snapshot.get("started_at"))
        finished_at = self._parse_optional_datetime(snapshot.get("finished_at"))

        return PostProcessFragmentsStatusResponse(
            is_running=bool(snapshot.get("is_running")),
            total_fragments=int(snapshot.get("total_fragments", 0)),
            processed_fragments=int(snapshot.get("processed_fragments", 0)),
            failed_fragments=int(snapshot.get("failed_fragments", 0)),
            current_fragment_id=snapshot.get("current_fragment_id"),
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


async def get_post_process_fragment_service(
        request: Request,
) -> PostProcessFragmentServiceInterface:
    try:
        return request.app.state.post_process_fragment_service
    except AttributeError:
        logger.error("PostProcessFragmentService is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostProcessFragmentService is not registered on the application state.",
        )
