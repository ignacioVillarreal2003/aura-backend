from abc import ABC, abstractmethod

from app.application.services.document_question_service.document_question_configuration import (
    DocumentQuestionConfiguration
)
from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question_response import DocumentQuestionResponse


class DocumentQuestionServiceInterface(ABC):
    @abstractmethod
    async def execute_document_question(self,
                                        document_question_request: DocumentQuestionRequest) -> DocumentQuestionResponse:
        pass

    @property
    @abstractmethod
    def configuration(self) -> DocumentQuestionConfiguration:
        pass

    @property
    @abstractmethod
    def is_llm_initialized(self) -> bool:
        pass
