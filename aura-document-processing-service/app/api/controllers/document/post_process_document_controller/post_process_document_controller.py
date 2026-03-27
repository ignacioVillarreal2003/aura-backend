import logging
from fastapi import APIRouter, Depends

from app.api.controllers.document.post_process_document_controller.interfaces.post_process_document_controller_interface import (
    PostProcessDocumentControllerInterface
)
from app.application.services.post_process_document_service.interfaces.post_process_document_service_interface import (
    PostProcessDocumentServiceInterface
)
from app.application.services.post_process_document_service.post_process_document_service import (
    get_post_process_document_service
)
from app.domain.dtos.post_process_document_controller.post_process_documents_request import (
    PostProcessDocumentsRequest
)
from app.domain.dtos.post_process_document_controller.post_process_start_response import PostProcessStartResponse
from app.domain.dtos.post_process_document_controller.post_process_status_response import PostProcessStatusResponse
from app.infrastructure.authentication_provider.authentication_provider import get_current_user
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse

logger = logging.getLogger(__name__)


class PostProcessDocumentController(PostProcessDocumentControllerInterface):
    async def start_all(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> PostProcessStartResponse:
        logger.info(
            "Start all post-processing request received",
            extra={"user_id": authenticated_user.id}
        )

        response = await post_process_document_service.start_all(authenticated_user=authenticated_user)

        logger.info(
            "Start all post-processing request completed",
            extra={"user_id": authenticated_user.id, "total_documents": response.total_documents}
        )

        return response

    async def start_for_documents(
            self,
            post_process_documents_request: PostProcessDocumentsRequest,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> PostProcessStartResponse:
        logger.info(
            "Start post-processing for specific documents request received",
            extra={
                "user_id": authenticated_user.id,
                "document_ids": post_process_documents_request.document_ids
            }
        )

        response = await post_process_document_service.start_for_documents(
            document_ids=post_process_documents_request.document_ids,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Start post-processing for specific documents request completed",
            extra={"user_id": authenticated_user.id, "total_documents": response.total_documents}
        )

        return response

    async def get_status(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> PostProcessStatusResponse:
        logger.info(
            "Post-processing status request received",
            extra={"user_id": authenticated_user.id}
        )

        return post_process_document_service.get_status()

    async def stop(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> dict:
        logger.info(
            "Stop post-processing request received",
            extra={"user_id": authenticated_user.id}
        )

        await post_process_document_service.stop()

        logger.info(
            "Stop post-processing request completed",
            extra={"user_id": authenticated_user.id}
        )

        return {"message": "Post-processing stop signal sent"}


router = APIRouter()

post_process_document_controller = PostProcessDocumentController()

router.post(
    "/start",
    response_model=PostProcessStartResponse
)(post_process_document_controller.start_all)

router.post(
    "/documents",
    response_model=PostProcessStartResponse
)(post_process_document_controller.start_for_documents)

router.get(
    "/status",
    response_model=PostProcessStatusResponse
)(post_process_document_controller.get_status)

router.post(
    "/stop"
)(post_process_document_controller.stop)
