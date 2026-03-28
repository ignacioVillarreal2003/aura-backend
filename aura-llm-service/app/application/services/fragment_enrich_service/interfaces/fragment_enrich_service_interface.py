from abc import ABC, abstractmethod

from app.domain.dtos.fragment_enrich.enrich_fragment_request import EnrichFragmentRequest
from app.domain.dtos.fragment_enrich.enrich_fragment_response import EnrichFragmentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class FragmentEnrichServiceInterface(ABC):
    @abstractmethod
    async def enrich_fragment(
            self,
            request: EnrichFragmentRequest,
            authenticated_user: AuthenticationResponse,
    ) -> EnrichFragmentResponse:
        pass
