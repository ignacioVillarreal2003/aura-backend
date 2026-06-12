from abc import ABC, abstractmethod
from starlette.responses import StreamingResponse

from app.application.services.user_interactions.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.user_interactions.document_question.document_question_response import DocumentQuestionResponse


class DocumentQuestionControllerInterface(ABC):
    @abstractmethod
    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            document_question_service: DocumentQuestionServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentQuestionResponse:
        pass

    @abstractmethod
    async def execute_document_question_stream(
            self,
            document_question_request: DocumentQuestionRequest,
            document_question_service: DocumentQuestionServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> StreamingResponse:
        pass
