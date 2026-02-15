from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.application.services.document_retrieve_service.interfaces.document_retrieve_service_interface import (
    DocumentRetrieveServiceInterface
)
from app.domain.dtos.document_retrieve.context_fragments_response import ContextFragmentsResponse
from app.domain.dtos.document_retrieve.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.document_retrieve.question_context_fragments_request import QuestionContextFragmentsRequest


class DocumentRetrieveControllerInterface(ABC):
    @abstractmethod
    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            document_retrieve_service: DocumentRetrieveServiceInterface,
            database_session: AsyncSession
    ) -> ContextFragmentsResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            document_retrieve_service: DocumentRetrieveServiceInterface,
            database_session: AsyncSession
    ) -> ContextFragmentsResponse:
        pass
