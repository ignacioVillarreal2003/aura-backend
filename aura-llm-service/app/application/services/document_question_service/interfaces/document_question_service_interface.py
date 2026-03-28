from abc import ABC, abstractmethod

from app.domain.dtos.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question.document_question_response import DocumentQuestionResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentQuestionServiceInterface(ABC):
    @abstractmethod
    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            authenticated_user: AuthenticationResponse,
    ) -> DocumentQuestionResponse:
        pass
