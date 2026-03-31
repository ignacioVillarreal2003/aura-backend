import logging
from fastapi import APIRouter, Depends, Response, status

from app.api.controllers.fragment_controllers.post_process_fragment_controller.interfaces.post_process_fragment_controller_interface import (
    PostProcessFragmentControllerInterface
)
from app.application.services.fragment.post_process_fragment_service.interfaces.post_process_fragment_service_interface import (
    PostProcessFragmentServiceInterface
)
from app.application.services.fragment.post_process_fragment_service.post_process_fragment_service import (
    get_post_process_fragment_service
)
from app.domain.dtos.fragment.post_process_fragment_controller.post_process_fragments_start_response import (
    PostProcessFragmentsStartResponse
)
from app.domain.dtos.fragment.post_process_fragment_controller.post_process_fragments_status_response import (
    PostProcessFragmentsStatusResponse
)
from app.domain.dtos.fragment.post_process_fragment_controller.post_process_fragments_request import (
    PostProcessFragmentsRequest
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class PostProcessFragmentController(PostProcessFragmentControllerInterface):
    async def start_all(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> PostProcessFragmentsStartResponse:
        logger.info(
            "Handling post-process all fragments request",
            extra={"user_id": authenticated_user.id},
        )

        post_process_fragments_start_response = await post_process_fragment_service.start_all(
            authenticated_user=authenticated_user
        )

        logger.info(
            "Post-process all fragments completed successfully",
            extra={
                "user_id": authenticated_user.id,
                "total_fragments": post_process_fragments_start_response.total_fragments
            },
        )

        return post_process_fragments_start_response

    async def start_for_documents(
            self,
            post_process_fragments_request: PostProcessFragmentsRequest,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> PostProcessFragmentsStartResponse:
        logger.info(
            "Handling post-process fragments for selected documents request",
            extra={"user_id": authenticated_user.id, "document_ids": post_process_fragments_request.document_ids},
        )

        post_process_fragments_start_response = await post_process_fragment_service.start_for_documents(
            post_process_fragments_request=post_process_fragments_request,
            authenticated_user=authenticated_user,
        )

        logger.info(
            "Post-process fragments for selected documents completed successfully",
            extra={
                "user_id": authenticated_user.id,
                "total_fragments": post_process_fragments_start_response.total_fragments
            },
        )

        return post_process_fragments_start_response

    async def get_status(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> PostProcessFragmentsStatusResponse:
        logger.info(
            "Handling fragment post-processing status request",
            extra={"user_id": authenticated_user.id},
        )

        post_process_fragments_status_response = post_process_fragment_service.get_status()

        logger.info(
            "Fragment post-processing status retrieved successfully",
            extra={
                "user_id": authenticated_user.id,
                "is_running": post_process_fragments_status_response.is_running,
                "total_fragments": post_process_fragments_status_response.total_fragments,
                "processed_fragments": post_process_fragments_status_response.processed_fragments,
                "failed_fragments": post_process_fragments_status_response.failed_fragments,
            },
        )

        return post_process_fragments_status_response

    async def stop(
            self,
            post_process_fragment_service: PostProcessFragmentServiceInterface = Depends(
                get_post_process_fragment_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> Response:
        logger.info(
            "Handling fragment post-processing stop request",
            extra={"user_id": authenticated_user.id},
        )

        await post_process_fragment_service.stop()

        logger.info(
            "Fragment post-processing stop completed successfully",
            extra={"user_id": authenticated_user.id},
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)


router = APIRouter()
post_process_fragment_controller = PostProcessFragmentController()

router.post("/start", response_model=PostProcessFragmentsStartResponse)(post_process_fragment_controller.start_all)

router.post("/documents", response_model=PostProcessFragmentsStartResponse)(
    post_process_fragment_controller.start_for_documents
)

router.get("/status", response_model=PostProcessFragmentsStatusResponse)(post_process_fragment_controller.get_status)

router.post("/stop")(post_process_fragment_controller.stop)
