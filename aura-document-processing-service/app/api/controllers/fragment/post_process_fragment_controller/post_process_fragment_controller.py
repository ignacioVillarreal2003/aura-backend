import logging
from fastapi import APIRouter, Depends

from app.api.controllers.fragment.post_process_fragment_controller.interfaces.post_process_fragment_controller_interface import (
    PostProcessFragmentControllerInterface
)
from app.application.services.post_process_fragment_service.interfaces.post_process_fragment_service_interface import (
    PostProcessFragmentServiceInterface
)
from app.application.services.post_process_fragment_service.post_process_fragment_service import (
    get_post_process_fragment_service
)
from app.domain.dtos.post_process_fragment_controller.post_process_fragments_request import PostProcessFragmentsRequest
from app.domain.dtos.post_process_fragment_controller.post_process_fragment_start_response import (
    PostProcessFragmentStartResponse
)
from app.domain.dtos.post_process_fragment_controller.post_process_fragment_status_response import (
    PostProcessFragmentStatusResponse
)
from app.infrastructure.authentication_provider.authentication_provider import get_current_user
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse

logger = logging.getLogger(__name__)


class PostProcessFragmentController(PostProcessFragmentControllerInterface):
    async def start_all(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> PostProcessFragmentStartResponse:
        logger.info(
            "Start all fragment post-processing request received",
            extra={"user_id": authenticated_user.id}
        )

        response = await post_process_fragment_service.start_all(authenticated_user=authenticated_user)

        logger.info(
            "Start all fragment post-processing request completed",
            extra={"user_id": authenticated_user.id, "total_fragments": response.total_fragments}
        )

        return response

    async def start_for_documents(
            self,
            post_process_fragments_request: PostProcessFragmentsRequest,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> PostProcessFragmentStartResponse:
        logger.info(
            "Start fragment post-processing for specific documents request received",
            extra={
                "user_id": authenticated_user.id,
                "document_ids": post_process_fragments_request.document_ids
            }
        )

        response = await post_process_fragment_service.start_for_documents(
            document_ids=post_process_fragments_request.document_ids,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Start fragment post-processing for specific documents request completed",
            extra={"user_id": authenticated_user.id, "total_fragments": response.total_fragments}
        )

        return response

    async def get_status(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> PostProcessFragmentStatusResponse:
        logger.info(
            "Fragment post-processing status request received",
            extra={"user_id": authenticated_user.id}
        )

        return post_process_fragment_service.get_status()

    async def stop(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> dict:
        logger.info(
            "Stop fragment post-processing request received",
            extra={"user_id": authenticated_user.id}
        )

        await post_process_fragment_service.stop()

        logger.info(
            "Stop fragment post-processing request completed",
            extra={"user_id": authenticated_user.id}
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
