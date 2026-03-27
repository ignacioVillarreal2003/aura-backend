import logging
from typing import Optional
from fastapi import APIRouter, Depends, Request

from app.api.controllers.controller_logging import log_controller
from app.api.controllers.document_question_controller.interfaces.document_question_controller_interface import (
    DocumentQuestionControllerInterface
)
from app.application.services.document_question_service.document_question_service import get_document_question_service
from app.application.services.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface
)
from app.domain.dtos.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question.document_question_response import DocumentQuestionResponse
from app.infrastructure.authentication_provider.authentication_provider import get_current_user
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse

logger = logging.getLogger(__name__)


class DocumentQuestionController(DocumentQuestionControllerInterface):
    async def execute_document_question(
            self,
            request: Request,
            document_question_request: DocumentQuestionRequest,
            document_question_service: DocumentQuestionServiceInterface = Depends(get_document_question_service),
            authenticated_user: AuthenticationResponse = Depends(get_current_user)
    ) -> DocumentQuestionResponse:
        log_controller(
            logger,
            operation="execute_document_question",
            phase="start",
            user_id=authenticated_user.id,
            message_count=len(document_question_request.messages),
        )

        authorization_token: Optional[str] = request.headers.get("Authorization")

        document_question_response = await document_question_service.execute_document_question(
            document_question_request=document_question_request,
            authenticated_user=authenticated_user,
            authorization_token=authorization_token
        )

        log_controller(
            logger,
            operation="execute_document_question",
            phase="success",
            user_id=authenticated_user.id,
            fragment_count=len(document_question_response.fragments),
            question_length=len(document_question_response.question or ""),
        )

        return document_question_response


router = APIRouter()

document_question_controller = DocumentQuestionController()

router.post(
    "",
    response_model=DocumentQuestionResponse,
)(document_question_controller.execute_document_question)
