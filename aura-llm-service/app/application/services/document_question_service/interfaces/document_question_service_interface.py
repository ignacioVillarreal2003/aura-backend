from abc import ABC, abstractmethod

from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question_response import DocumentQuestionResponse


class DocumentQuestionServiceInterface(ABC):
    @abstractmethod
    async def execute_document_question(self,
                                        request_body: DocumentQuestionRequest) -> DocumentQuestionResponse:
        pass
