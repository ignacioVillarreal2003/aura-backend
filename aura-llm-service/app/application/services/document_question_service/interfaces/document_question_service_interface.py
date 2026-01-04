from abc import ABC, abstractmethod
from typing import List, Optional

from app.application.services.document_question_service.document_question_configuration import (
    DocumentQuestionConfiguration
)
from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question_response import DocumentQuestionResponse


class DocumentQuestionServiceInterface(ABC):
    @abstractmethod
    async def execute_document_question(self,
                                        request_body: DocumentQuestionRequest) -> DocumentQuestionResponse:
        pass

    @abstractmethod
    async def retrieve_fragments_by_question(self,
                                             question: str,
                                             fragments_count: Optional[int] = None) -> List[str]:
        pass

    @property
    @abstractmethod
    def configuration(self) -> DocumentQuestionConfiguration:
        pass

    @property
    @abstractmethod
    def is_llm_initialized(self) -> bool:
        pass
