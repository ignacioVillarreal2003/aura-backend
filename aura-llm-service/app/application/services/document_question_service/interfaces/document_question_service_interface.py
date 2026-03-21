from abc import ABC, abstractmethod
from typing import Optional

from app.domain.dtos.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question.document_question_response import DocumentQuestionResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentQuestionServiceInterface(ABC):
    @abstractmethod
    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            user: AuthenticationResponse,
            authorization: Optional[str] = None
    ) -> DocumentQuestionResponse:
        pass
