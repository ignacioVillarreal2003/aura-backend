from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.application.services.fragment.fragment_query_service.interfaces.fragment_query_service_interface import (
    FragmentQueryServiceInterface,
)
from app.domain.dtos.fragment.fragment_query.documents_context_fragments_request import (
    DocumentsContextFragmentsRequest,
)
from app.domain.dtos.fragment.fragment_query.fragment_list_response import FragmentListResponse
from app.domain.dtos.fragment.fragment_query.question_context_fragments_request import (
    QuestionContextFragmentsRequest,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser


class FragmentQueryControllerInterface(ABC):
    @abstractmethod
    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            fragment_query_service: FragmentQueryServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> FragmentListResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_documents(
            self,
            documents_context_fragments_request: DocumentsContextFragmentsRequest,
            fragment_query_service: FragmentQueryServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> FragmentListResponse:
        pass
