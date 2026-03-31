import logging
from fastapi import APIRouter, Depends, Response, status

from app.api.controllers.document_controllers.post_process_document_controller.interfaces.post_process_document_controller_interface import (
    PostProcessDocumentControllerInterface
)
from app.application.services.document.post_process_document_service.interfaces.post_process_document_service_interface import (
    PostProcessDocumentServiceInterface
)
from app.application.services.document.post_process_document_service.post_process_document_service import (
    get_post_process_document_service
)
from app.domain.dtos.document.post_process_document_controller.post_process_documents_start_response import (
    PostProcessDocumentsStartResponse
)
from app.domain.dtos.document.post_process_document_controller.post_process_documents_request import (
    PostProcessDocumentsRequest
)
from app.domain.dtos.document.post_process_document_controller.post_process_documents_status_response import (
    PostProcessDocumentsStatusResponse
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class PostProcessDocumentController(PostProcessDocumentControllerInterface):
    async def start_all(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> PostProcessDocumentsStartResponse:
        logger.info(
            "Handling post-process all documents request",
            extra={"user_id": authenticated_user.id},
        )

        post_process_documents_start_response = await post_process_document_service.start_all(
            authenticated_user=authenticated_user)

        logger.info(
            "Post-process all documents completed successfully",
            extra={"user_id": authenticated_user.id,
                   "total_documents": post_process_documents_start_response.total_documents},
        )

        return post_process_documents_start_response

    async def start_for_documents(
            self,
            post_process_documents_request: PostProcessDocumentsRequest,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> PostProcessDocumentsStartResponse:
        logger.info(
            "Handling post-process selected documents request",
            extra={"user_id": authenticated_user.id, "document_ids": post_process_documents_request.document_ids},
        )

        post_process_documents_start_response = await post_process_document_service.start_for_documents(
            post_process_documents_request=post_process_documents_request,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Post-process selected documents completed successfully",
            extra={"user_id": authenticated_user.id,
                   "total_documents": post_process_documents_start_response.total_documents},
        )

        return post_process_documents_start_response

    async def get_status(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> PostProcessDocumentsStatusResponse:
        logger.info(
            "Handling document post-processing status request",
            extra={"user_id": authenticated_user.id},
        )

        post_process_documents_status_response = post_process_document_service.get_status()

        logger.info(
            "Document post-processing status retrieved successfully",
            extra={
                "user_id": authenticated_user.id,
                "is_running": post_process_documents_status_response.is_running,
                "total_documents": post_process_documents_status_response.total_documents,
                "processed_documents": post_process_documents_status_response.processed_documents,
                "failed_documents": post_process_documents_status_response.failed_documents,
            },
        )

        return post_process_documents_status_response

    async def stop(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> Response:
        logger.info(
            "Handling document post-processing stop request",
            extra={"user_id": authenticated_user.id},
        )

        await post_process_document_service.stop()

        logger.info(
            "Document post-processing stop completed successfully",
            extra={"user_id": authenticated_user.id},
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)


router = APIRouter()
post_process_document_controller = PostProcessDocumentController()

router.post("/start", response_model=PostProcessDocumentsStartResponse)(post_process_document_controller.start_all)

router.post("/documents", response_model=PostProcessDocumentsStartResponse)(
    post_process_document_controller.start_for_documents
)

router.get("/status", response_model=PostProcessDocumentsStatusResponse)(post_process_document_controller.get_status)

router.post("/stop")(post_process_document_controller.stop)
