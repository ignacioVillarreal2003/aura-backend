from abc import ABC, abstractmethod
from typing import Optional

from app.infrastructure.http.llm_provider.dtos.classify_document_response import ClassifyDocumentResponse
from app.infrastructure.http.llm_provider.dtos.enrich_fragment_response import EnrichFragmentResponse


class LlmProviderInterface(ABC):
    @abstractmethod
    async def classify_document(
            self,
            document_name: str,
            content: str,
            authenticated_user: Optional[AuthenticatedUserResponse] = None
    ) -> ClassifyDocumentResponse:
        pass

    @abstractmethod
    async def enrich_fragment(
            self,
            content: str,
            authenticated_user: Optional[AuthenticationResponse] = None
    ) -> EnrichFragmentResponse:
        pass
