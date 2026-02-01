from abc import abstractmethod, ABC
from sqlalchemy.orm.session import Session

from app.domain.dtos.context_fragments_response import ContextFragmentsResponse
from app.domain.dtos.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.question_context_fragments_request import QuestionContextFragmentsRequest


class DocumentContextServiceInterface(ABC):
    @abstractmethod
    def execute_retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            db: Session
    ) -> ContextFragmentsResponse:
        pass

    @abstractmethod
    def execute_retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            db: Session
    ) -> ContextFragmentsResponse:
        pass
