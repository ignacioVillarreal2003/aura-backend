import logging

from fastapi import APIRouter, Depends

from app.api.controllers.controller_logging import log_controller
from app.api.controllers.fragment_enrich_controller.interfaces.fragment_enrich_controller_interface import (
    FragmentEnrichControllerInterface,
)
from app.application.services.fragment_enrich_service.fragment_enrich_service import get_fragment_enrich_service
from app.application.services.fragment_enrich_service.interfaces.fragment_enrich_service_interface import (
    FragmentEnrichServiceInterface,
)
from app.domain.dtos.fragment_enrich.enrich_fragment_request import EnrichFragmentRequest
from app.domain.dtos.fragment_enrich.enrich_fragment_response import EnrichFragmentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.authentication_provider.service_authentication_provider import get_service_caller_user

logger = logging.getLogger(__name__)


class FragmentEnrichController(FragmentEnrichControllerInterface):
    async def enrich_fragment(
            self,
            body: EnrichFragmentRequest,
            fragment_enrich_service: FragmentEnrichServiceInterface = Depends(get_fragment_enrich_service),
            authenticated_user: AuthenticationResponse = Depends(get_service_caller_user),
    ) -> EnrichFragmentResponse:
        log_controller(
            logger,
            operation="enrich_fragment",
            phase="start",
            user_id=authenticated_user.id,
            content_length=len(body.content or ""),
        )

        response = await fragment_enrich_service.enrich_fragment(
            request=body,
            authenticated_user=authenticated_user,
        )

        log_controller(
            logger,
            operation="enrich_fragment",
            phase="success",
            user_id=authenticated_user.id,
            topics_count=len(response.topics),
        )

        return response


router = APIRouter()

fragment_enrich_controller = FragmentEnrichController()

router.post(
    "",
    response_model=EnrichFragmentResponse,
)(fragment_enrich_controller.enrich_fragment)
