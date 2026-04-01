import logging
from fastapi import APIRouter, Depends

from app.api.controllers.general.document_question_controller.interfaces.document_question_controller_interface import (
    DocumentQuestionControllerInterface
)
from app.application.services.general.document_question_service.document_question_service import get_document_question_service
from app.application.services.general.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.general.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.general.document_question.document_question_response import DocumentQuestionResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class DocumentQuestionController(DocumentQuestionControllerInterface):
    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            document_question_service: DocumentQuestionServiceInterface = Depends(get_document_question_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> DocumentQuestionResponse:
        document_question_response = await document_question_service.execute_document_question(
            document_question_request=document_question_request,
            authenticated_user=authenticated_user,
        )

        return document_question_response


router = APIRouter()
document_question_controller = DocumentQuestionController()

router.post(
    "",
    response_model=DocumentQuestionResponse,
)(document_question_controller.execute_document_question)
