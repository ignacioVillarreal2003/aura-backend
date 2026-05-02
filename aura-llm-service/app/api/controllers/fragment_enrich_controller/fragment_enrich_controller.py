import logging

from fastapi import APIRouter, Depends

from app.api.dependencies.idempotency import optional_idempotency_key
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.controllers.fragment_enrich_controller.fragment_enrich_controller_interface import (
    FragmentEnrichControllerInterface
)
from app.api.openapi.common import default_error_responses
from app.application.services.fragment_enrich_service.fragment_enrich_service import get_fragment_enrich_service
from app.application.services.fragment_enrich_service.interfaces.fragment_enrich_service_interface import (
    FragmentEnrichServiceInterface
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.fragment_enrich.enrich_fragment_request import EnrichFragmentRequest
from app.domain.dtos.fragment_enrich.enrich_fragment_response import EnrichFragmentResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class FragmentEnrichController(FragmentEnrichControllerInterface):
    async def enrich_fragment(
            self,
            enrich_fragment_request: EnrichFragmentRequest,
            fragment_enrich_service: FragmentEnrichServiceInterface = Depends(get_fragment_enrich_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _idemp: None = Depends(optional_idempotency_key),
            _rl: None = Depends(default_rate_limit),
    ) -> EnrichFragmentResponse:
        logger.info(
            "Handling enrich fragment request",
            extra={
                "user_id": authenticated_user.id
            }
        )

        enrich_fragment_response = await fragment_enrich_service.enrich_fragment(
            enrich_fragment_request=enrich_fragment_request,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Enrich fragment completed successfully",
            extra={
                "user_id": authenticated_user.id
            }
        )

        return enrich_fragment_response


router = APIRouter()
fragment_enrich_controller = FragmentEnrichController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Fragmento enriquecido",
        "model": EnrichFragmentResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    fragment_enrich_controller.enrich_fragment,
    methods=["POST"],
    response_model=EnrichFragmentResponse,
    operation_id="enrichFragment",
    summary="Enriquecer fragmento",
    description="Genera metadatos enriquecidos para un fragmento de documento usando el LLM.",
    responses=_response,
)
