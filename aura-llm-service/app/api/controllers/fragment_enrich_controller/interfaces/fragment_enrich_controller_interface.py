from abc import ABC, abstractmethod

from app.application.services.fragment_enrich_service.interfaces.fragment_enrich_service_interface import (
    FragmentEnrichServiceInterface,
)
from app.domain.dtos.fragment_enrich.enrich_fragment_request import EnrichFragmentRequest
from app.domain.dtos.fragment_enrich.enrich_fragment_response import EnrichFragmentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class FragmentEnrichControllerInterface(ABC):
    @abstractmethod
    async def enrich_fragment(
            self,
            body: EnrichFragmentRequest,
            fragment_enrich_service: FragmentEnrichServiceInterface,
            authenticated_user: AuthenticationResponse,
    ) -> EnrichFragmentResponse:
        pass
