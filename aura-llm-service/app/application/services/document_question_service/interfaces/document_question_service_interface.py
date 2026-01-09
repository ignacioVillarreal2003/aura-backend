from abc import ABC, abstractmethod
from typing import List, Optional

from app.application.services.document_question_service.document_question_configuration import (
    DocumentQuestionConfiguration
)
from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question_response import DocumentQuestionResponse
from app.domain.dtos.message import Message


class DocumentQuestionServiceInterface(ABC):
    @abstractmethod
    async def execute_document_question(self,
                                        request: DocumentQuestionRequest) -> DocumentQuestionResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_question(self,
                                                     question: str,
                                                     context_fragments_count: Optional[int] = None) -> List[str]:
        pass

    @abstractmethod
    async def answer_question(self,
                              question: str,
                              history_messages: Optional[list[Message]] = None,
                              context_fragments: Optional[List[str]] = None) -> str:
        pass

    @property
    @abstractmethod
    def configuration(self) -> DocumentQuestionConfiguration:
        pass

    @property
    @abstractmethod
    def is_llm_initialized(self) -> bool:
        pass
