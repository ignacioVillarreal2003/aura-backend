from abc import ABC, abstractmethod

from app.application.services.support.fragment_enrich_service.interfaces.fragment_enrich_service_interface import (
    FragmentEnrichServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.fragment_enrich.enrich_fragment_request import EnrichFragmentRequest
from app.domain.dtos.fragment_enrich.enrich_fragment_response import EnrichFragmentResponse


class FragmentEnrichControllerInterface(ABC):
    @abstractmethod
    async def enrich_fragment(
            self,
            enrich_fragment_request: EnrichFragmentRequest,
            fragment_enrich_service: FragmentEnrichServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> EnrichFragmentResponse:
        pass
