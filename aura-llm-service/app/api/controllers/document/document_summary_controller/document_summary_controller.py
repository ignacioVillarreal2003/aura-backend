import logging
from fastapi import APIRouter, Depends

from app.api.controllers.document.document_summary_controller.interfaces.document_summary_controller_interface import (
    DocumentSummaryControllerInterface
)
from app.application.services.document.document_summary_service.document_summary_service import get_document_summary_service
from app.application.services.document.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document.document_summary.document_summary_response import DocumentSummaryResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class DocumentSummaryController(DocumentSummaryControllerInterface):
    async def execute_document_summary(
            self,
            document_summary_request: DocumentSummaryRequest,
            document_summary_service: DocumentSummaryServiceInterface = Depends(get_document_summary_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> DocumentSummaryResponse:
        logger.info(
            "Handling document summary request",
            extra={
                "user_id": authenticated_user.id
            }
        )

        document_summary_response = await document_summary_service.execute_document_summary(
            document_summary_request=document_summary_request,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Document summary completed successfully",
            extra={
                "user_id": authenticated_user.id
            }
        )

        return document_summary_response


router = APIRouter()
document_summary_controller = DocumentSummaryController()

router.post(
    "",
    response_model=DocumentSummaryResponse,
)(document_summary_controller.execute_document_summary)
