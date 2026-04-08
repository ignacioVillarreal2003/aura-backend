from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.support.fragment_enrich.enrich_fragment_request import EnrichFragmentRequest
from app.domain.dtos.support.fragment_enrich.enrich_fragment_response import EnrichFragmentResponse


class FragmentEnrichServiceInterface(ABC):
    @abstractmethod
    async def enrich_fragment(
            self,
            enrich_fragment_request: EnrichFragmentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> EnrichFragmentResponse:
        pass
