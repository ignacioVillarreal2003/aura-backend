from abc import ABC, abstractmethod

from sqlalchemy.orm.session import Session

from app.application.services.interfaces.document_context_service_interface import DocumentContextServiceInterface
from app.domain.dtos.context_fragments_response import ContextFragmentsResponse
from app.domain.dtos.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.question_context_fragments_request import QuestionContextFragmentsRequest


class DocumentContextControllerInterface(ABC):
    @abstractmethod
    async def execute_retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            document_context_service: DocumentContextServiceInterface,
            db: Session
    ) -> ContextFragmentsResponse:
        pass

    @abstractmethod
    async def execute_retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            document_context_service: DocumentContextServiceInterface,
            db: Session
    ) -> ContextFragmentsResponse:
        pass
