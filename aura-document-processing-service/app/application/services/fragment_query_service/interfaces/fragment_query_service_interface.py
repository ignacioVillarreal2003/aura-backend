from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.document_query_controller.context_fragment_response import ContextFragmentListResponse
from app.domain.dtos.document_query_controller.question_context_fragments_request import QuestionContextFragmentsRequest
from app.domain.dtos.fragment_query_controller.documents_context_fragments_request import DocumentsContextFragmentsRequest
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class FragmentQueryServiceInterface(ABC):
    @abstractmethod
    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> ContextFragmentListResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_documents(
            self,
            documents_context_fragments_request: DocumentsContextFragmentsRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> ContextFragmentListResponse:
        pass
