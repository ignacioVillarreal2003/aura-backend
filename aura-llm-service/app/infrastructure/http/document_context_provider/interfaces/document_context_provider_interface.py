from abc import ABC, abstractmethod
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_context_provider.dtos.fragment_list_response import FragmentListResponse


class DocumentContextProviderInterface(ABC):
    @abstractmethod
    async def retrieve_context_fragments_by_question(
            self,
            authenticated_user: AuthenticatedUser,
            question: str,
            question_max_fragments: int,
            use_keywords: Optional[bool] = None,
            keywords: Optional[str] = None,
            keywords_max_fragments: Optional[int] = None,
            use_rerank: Optional[bool] = None,
            rerank_max_fragments: Optional[int] = None
    ) -> FragmentListResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_document(
            self,
            authenticated_user: AuthenticatedUser,
            document_ids: list[int]
    ) -> FragmentListResponse:
        pass
