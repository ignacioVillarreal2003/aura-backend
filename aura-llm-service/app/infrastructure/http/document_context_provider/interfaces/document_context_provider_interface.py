from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_context_provider.dtos.fragment_list_response import FragmentListResponse
from app.infrastructure.http.document_context_provider.dtos.question_context_fragments_request import (
    QuestionContextFragmentsRequest,
)


class DocumentContextProviderInterface(ABC):
    @abstractmethod
    async def retrieve_context_fragments_by_question_request(
            self,
            authenticated_user: AuthenticatedUser,
            request: QuestionContextFragmentsRequest,
    ) -> FragmentListResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_document(
            self,
            authenticated_user: AuthenticatedUser,
            document_ids: list[int],
    ) -> FragmentListResponse:
        pass
