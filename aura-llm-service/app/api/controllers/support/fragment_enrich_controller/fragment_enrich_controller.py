import logging

from fastapi import APIRouter, Depends

from app.api.controllers.support.fragment_enrich_controller.interfaces.fragment_enrich_controller_interface import (
    FragmentEnrichControllerInterface
)
from app.application.services.support.fragment_enrich_service.fragment_enrich_service import get_fragment_enrich_service
from app.application.services.support.fragment_enrich_service.interfaces.fragment_enrich_service_interface import (
    FragmentEnrichServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.support.fragment_enrich.enrich_fragment_request import EnrichFragmentRequest
from app.domain.dtos.support.fragment_enrich.enrich_fragment_response import EnrichFragmentResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class FragmentEnrichController(FragmentEnrichControllerInterface):
    async def enrich_fragment(
            self,
            enrich_fragment_request: EnrichFragmentRequest,
            fragment_enrich_service: FragmentEnrichServiceInterface = Depends(get_fragment_enrich_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> EnrichFragmentResponse:
        enrich_fragment_response = await fragment_enrich_service.enrich_fragment(
            enrich_fragment_request=enrich_fragment_request,
            authenticated_user=authenticated_user,
        )

        return enrich_fragment_response


router = APIRouter()
fragment_enrich_controller = FragmentEnrichController()

router.post(
    "",
    response_model=EnrichFragmentResponse,
)(fragment_enrich_controller.enrich_fragment)
