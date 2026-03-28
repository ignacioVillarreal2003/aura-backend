from abc import ABC, abstractmethod
from typing import Optional

from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.document_context_provider.dtos.context_fragments_response import ContextFragmentListResponse


class DocumentContextProviderInterface(ABC):
    @abstractmethod
    async def retrieve_context_fragments_by_question(
            self,
            question: str,
            max_context_fragments: int,
            authenticated_user: Optional[AuthenticationResponse] = None
    ) -> ContextFragmentListResponse:
        pass

    @abstractmethod
    async def retrieve_context_fragments_by_document(
            self,
            document_id: int,
            authenticated_user: Optional[AuthenticationResponse] = None
    ) -> ContextFragmentListResponse:
        pass
