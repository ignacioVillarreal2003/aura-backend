import logging
from fastapi import APIRouter, Depends, Response, status

from app.api.controllers.controller_logging import log_controller
from app.api.controllers.document.post_process_document_controller.interfaces.post_process_document_controller_interface import (
    PostProcessDocumentControllerInterface
)
from app.application.services.document.post_process_document_service.interfaces.post_process_document_service_interface import (
    PostProcessDocumentServiceInterface
)
from app.application.services.document.post_process_document_service.post_process_document_service import (
    get_post_process_document_service
)
from app.domain.dtos.document.post_process_document_controller.post_process_document_start_response import \
    PostProcessDocumentStartResponse
from app.domain.dtos.document.post_process_document_controller.post_process_documents_request import (
    PostProcessDocumentsRequest
)
from app.domain.dtos.document.post_process_document_controller.post_process_document_status_response import \
    PostProcessStatusResponse
from app.domain.models.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class PostProcessDocumentController(PostProcessDocumentControllerInterface):
    async def start_all(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> PostProcessDocumentStartResponse:
        log_controller(
            logger,
            operation="post_process_document_start_all",
            phase="start",
            user_id=authenticated_user.id,
        )

        response = await post_process_document_service.start_all(authenticated_user=authenticated_user)

        log_controller(
            logger,
            operation="post_process_document_start_all",
            phase="success",
            user_id=authenticated_user.id,
            total_documents=response.total_documents,
        )

        return response

    async def start_for_documents(
            self,
            post_process_documents_request: PostProcessDocumentsRequest,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> PostProcessDocumentStartResponse:
        log_controller(
            logger,
            operation="post_process_document_start_for_documents",
            phase="start",
            user_id=authenticated_user.id,
            document_ids=post_process_documents_request.document_ids,
        )

        response = await post_process_document_service.start_for_documents(
            document_ids=post_process_documents_request.document_ids,
            authenticated_user=authenticated_user
        )

        log_controller(
            logger,
            operation="post_process_document_start_for_documents",
            phase="success",
            user_id=authenticated_user.id,
            total_documents=response.total_documents,
        )

        return response

    async def get_status(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> PostProcessStatusResponse:
        log_controller(
            logger,
            operation="post_process_document_get_status",
            phase="start",
            user_id=authenticated_user.id,
        )

        status_response = post_process_document_service.get_status()

        log_controller(
            logger,
            operation="post_process_document_get_status",
            phase="success",
            user_id=authenticated_user.id,
            is_running=status_response.is_running,
            total_documents=status_response.total_documents,
            processed_documents=status_response.processed_documents,
            failed_documents=status_response.failed_documents,
        )

        return status_response

    async def stop(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface = Depends(
                get_post_process_document_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> Response:
        log_controller(
            logger,
            operation="post_process_document_stop",
            phase="start",
            user_id=authenticated_user.id,
        )

        await post_process_document_service.stop()

        log_controller(
            logger,
            operation="post_process_document_stop",
            phase="success",
            user_id=authenticated_user.id,
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)


router = APIRouter()

post_process_document_controller = PostProcessDocumentController()

router.post(
    "/start",
    response_model=PostProcessDocumentStartResponse
)(post_process_document_controller.start_all)

router.post(
    "/documents",
    response_model=PostProcessDocumentStartResponse
)(post_process_document_controller.start_for_documents)

router.get(
    "/status",
    response_model=PostProcessStatusResponse
)(post_process_document_controller.get_status)

router.post(
    "/stop"
)(post_process_document_controller.stop)
