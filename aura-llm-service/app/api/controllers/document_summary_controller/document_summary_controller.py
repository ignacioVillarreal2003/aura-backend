import logging
from typing import Optional
from fastapi import APIRouter, Depends, Request

from app.api.controllers.controller_logging import log_controller
from app.api.controllers.document_summary_controller.interfaces.document_summary_controller_interface import (
    DocumentSummaryControllerInterface
)
from app.application.services.document_summary_service.document_summary_service import get_document_summary_service
from app.application.services.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface
)
from app.domain.dtos.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary.document_summary_response import DocumentSummaryResponse
from app.infrastructure.authentication_provider.authentication_provider import get_current_user
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse

logger = logging.getLogger(__name__)


class DocumentSummaryController(DocumentSummaryControllerInterface):
    async def execute_document_summary(
            self,
            request: Request,
            document_summary_request: DocumentSummaryRequest,
            document_summary_service: DocumentSummaryServiceInterface = Depends(get_document_summary_service),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> DocumentSummaryResponse:
        log_controller(
            logger,
            operation="execute_document_summary",
            phase="start",
            user_id=authenticated_user.id,
            document_id=document_summary_request.document_id,
        )

        authorization_token: Optional[str] = request.headers.get("Authorization")

        document_summary_response = await document_summary_service.execute_document_summary(
            document_summary_request=document_summary_request,
            authenticated_user=authenticated_user,
            authorization_token=authorization_token
        )

        log_controller(
            logger,
            operation="execute_document_summary",
            phase="success",
            user_id=authenticated_user.id,
            document_id=document_summary_response.document_id,
            fragment_count=len(document_summary_response.fragments),
        )

        return document_summary_response


router = APIRouter()

document_summary_controller = DocumentSummaryController()

router.post(
    "",
    response_model=DocumentSummaryResponse,
)(document_summary_controller.execute_document_summary)
