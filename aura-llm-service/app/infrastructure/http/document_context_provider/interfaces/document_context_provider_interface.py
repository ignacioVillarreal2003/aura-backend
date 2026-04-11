from abc import ABC, abstractmethod
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_context_provider.dtos.fragment_list_response import FragmentListResponse


class DocumentContextProviderInterface(ABC):
    @abstractmethod
    async def retrieve_context_fragments_by_question(
            self,
            question: str,
            max_fragments: int,
            authenticated_user: Optional[AuthenticatedUser] = None,
            *,
            search_keywords: Optional[str] = None,
            use_rerank: bool = False,
            rerank_final_fragments: Optional[int] = None,
    ) -> FragmentListResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_document(
            self,
            document_ids: list[int],
            authenticated_user: Optional[AuthenticatedUser] = None
    ) -> FragmentListResponse:
        pass
