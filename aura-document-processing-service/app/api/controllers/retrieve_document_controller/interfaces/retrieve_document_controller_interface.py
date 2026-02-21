from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.application.services.retrieve_document_service.interfaces.retrieve_document_service_interface import (
    RetrieveDocumentServiceInterface
)
from app.domain.dtos.retrieve_document.context_fragments_response import ContextFragmentsResponse
from app.domain.dtos.retrieve_document.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.retrieve_document.question_context_fragments_request import QuestionContextFragmentsRequest


class RetrieveDocumentControllerInterface(ABC):
    @abstractmethod
    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            retrieve_document_service: RetrieveDocumentServiceInterface,
            database_session: AsyncSession
    ) -> ContextFragmentsResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            retrieve_document_service: RetrieveDocumentServiceInterface,
            database_session: AsyncSession
    ) -> ContextFragmentsResponse:
        pass
