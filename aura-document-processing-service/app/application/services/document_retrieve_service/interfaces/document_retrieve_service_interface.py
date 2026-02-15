from abc import ABC, abstractmethod
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.document_retrieve.context_fragments_response import ContextFragmentsResponse
from app.domain.dtos.document_retrieve.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.document_retrieve.question_context_fragments_request import QuestionContextFragmentsRequest


class DocumentRetrieveServiceInterface(ABC):
    @abstractmethod
    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            database_session: AsyncSession
    ) -> ContextFragmentsResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            database_session: AsyncSession
    ) -> ContextFragmentsResponse:
        pass

    @abstractmethod
    def get_metrics(
            self
    ) -> Dict[str, int]:
        pass
