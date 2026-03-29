from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.fragment.fragment_query_controller.documents_context_fragments_request import (
    DocumentsContextFragmentsRequest
)
from app.domain.dtos.fragment.fragment_query_controller.fragment_list_response import FragmentListResponse
from app.domain.dtos.fragment.fragment_query_controller.question_context_fragments_request import QuestionContextFragmentsRequest
from app.domain.models.authenticated_user import AuthenticatedUser


class FragmentQueryServiceInterface(ABC):
    @abstractmethod
    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> FragmentListResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_documents(
            self,
            documents_context_fragments_request: DocumentsContextFragmentsRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> FragmentListResponse:
        pass
