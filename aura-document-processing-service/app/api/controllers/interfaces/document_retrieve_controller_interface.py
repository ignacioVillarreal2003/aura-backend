from abc import ABC, abstractmethod
from sqlalchemy.orm.session import Session

from app.application.services.document_retrieve_service.interfaces.document_context_service_interface import (
    DocumentContextServiceInterface
)
from app.domain.dtos.document_retrieve.context_fragments_response import ContextFragmentsResponse
from app.domain.dtos.document_retrieve.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.document_retrieve.question_context_fragments_request import QuestionContextFragmentsRequest


class DocumentRetrieveControllerInterface(ABC):
    @abstractmethod
    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            document_context_service: DocumentContextServiceInterface,
            db: Session
    ) -> ContextFragmentsResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            document_context_service: DocumentContextServiceInterface,
            db: Session
    ) -> ContextFragmentsResponse:
        pass
