from abc import ABC, abstractmethod
from typing import List, Optional

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
                                                     max_context_fragments_count: Optional[int] = None) -> List[str]:
        pass

    @abstractmethod
    async def generate_answer(self,
                              question: str,
                              history_messages: Optional[List[Message]],
                              context_fragments: Optional[List[str]]) -> str:
        pass
