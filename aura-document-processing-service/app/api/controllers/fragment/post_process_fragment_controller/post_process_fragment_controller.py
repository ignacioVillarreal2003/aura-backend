import logging
from fastapi import APIRouter, Depends

from app.api.controllers.controller_logging import log_controller
from app.api.controllers.fragment.post_process_fragment_controller.interfaces.post_process_fragment_controller_interface import (
    PostProcessFragmentControllerInterface
)
from app.application.services.fragment.post_process_fragment_service.interfaces.post_process_fragment_service_interface import (
    PostProcessFragmentServiceInterface
)
from app.application.services.fragment.post_process_fragment_service.post_process_fragment_service import (
    get_post_process_fragment_service
)
from app.domain.dtos.fragment.post_process_fragment_controller.post_process_fragment_start_response import (
    PostProcessFragmentStartResponse
)
from app.domain.dtos.fragment.post_process_fragment_controller.post_process_fragment_status_response import (
    PostProcessFragmentStatusResponse
)
from app.domain.dtos.fragment.post_process_fragment_controller.post_process_fragments_request import (
    PostProcessFragmentsRequest
)
from app.domain.models.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class PostProcessFragmentController(PostProcessFragmentControllerInterface):
    async def start_all(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> PostProcessFragmentStartResponse:
        log_controller(
            logger,
            operation="post_process_fragment_start_all",
            phase="start",
            user_id=authenticated_user.id,
        )

        response = await post_process_fragment_service.start_all(authenticated_user=authenticated_user)

        log_controller(
            logger,
            operation="post_process_fragment_start_all",
            phase="success",
            user_id=authenticated_user.id,
            total_fragments=response.total_fragments,
        )

        return response

    async def start_for_documents(
            self,
            post_process_fragments_request: PostProcessFragmentsRequest,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> PostProcessFragmentStartResponse:
        log_controller(
            logger,
            operation="post_process_fragment_start_for_documents",
            phase="start",
            user_id=authenticated_user.id,
            document_ids=post_process_fragments_request.document_ids,
        )

        response = await post_process_fragment_service.start_for_documents(
            document_ids=post_process_fragments_request.document_ids,
            authenticated_user=authenticated_user
        )

        log_controller(
            logger,
            operation="post_process_fragment_start_for_documents",
            phase="success",
            user_id=authenticated_user.id,
            total_fragments=response.total_fragments,
        )

        return response

    async def get_status(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> PostProcessFragmentStatusResponse:
        log_controller(
            logger,
            operation="post_process_fragment_get_status",
            phase="start",
            user_id=authenticated_user.id,
        )

        status_response = post_process_fragment_service.get_status()

        log_controller(
            logger,
            operation="post_process_fragment_get_status",
            phase="success",
            user_id=authenticated_user.id,
            is_running=status_response.is_running,
            total_fragments=status_response.total_fragments,
            processed_fragments=status_response.processed_fragments,
            failed_fragments=status_response.failed_fragments,
        )

        return status_response

    async def stop(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> dict:
        log_controller(
            logger,
            operation="post_process_fragment_stop",
            phase="start",
            user_id=authenticated_user.id,
        )

        await post_process_fragment_service.stop()

        log_controller(
            logger,
            operation="post_process_fragment_stop",
            phase="success",
            user_id=authenticated_user.id,
        )

        return {"message": "Fragment post-processing stop signal sent"}


router = APIRouter()

post_process_fragment_controller = PostProcessFragmentController()

router.post(
    "/start",
    response_model=PostProcessFragmentStartResponse
)(post_process_fragment_controller.start_all)

router.post(
    "/documents",
    response_model=PostProcessFragmentStartResponse
)(post_process_fragment_controller.start_for_documents)

router.get(
    "/status",
    response_model=PostProcessFragmentStatusResponse
)(post_process_fragment_controller.get_status)

router.post(
    "/stop"
)(post_process_fragment_controller.stop)
