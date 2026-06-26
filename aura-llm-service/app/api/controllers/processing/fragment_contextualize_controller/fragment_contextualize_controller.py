from fastapi import APIRouter, Depends

from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.controllers.processing.fragment_contextualize_controller.fragment_contextualize_controller_interface import (
    FragmentContextualizeControllerInterface,
)
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_fragment_contextualize_service
from app.application.services.processing.fragment_contextualize_service.interfaces.fragment_contextualize_service_interface import (
    FragmentContextualizeServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.fragment_contextualize.contextualize_fragment_request import (
    ContextualizeFragmentRequest,
)
from app.domain.dtos.processing.fragment_contextualize.contextualize_fragment_response import (
    ContextualizeFragmentResponse,
)
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class FragmentContextualizeController(FragmentContextualizeControllerInterface):
    async def contextualize_fragment(
            self,
            contextualize_fragment_request: ContextualizeFragmentRequest,
            fragment_contextualize_service: FragmentContextualizeServiceInterface = Depends(
                get_fragment_contextualize_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> ContextualizeFragmentResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_FRAGMENT_CONTEXTUALIZE}),
        )

        return await fragment_contextualize_service.contextualize_fragment(
            contextualize_fragment_request=contextualize_fragment_request,
            authenticated_user=authenticated_user,
        )


router = APIRouter()
fragment_contextualize_controller = FragmentContextualizeController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Fragmento contextualizado",
        "model": ContextualizeFragmentResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    fragment_contextualize_controller.contextualize_fragment,
    methods=["POST"],
    response_model=ContextualizeFragmentResponse,
    operation_id="contextualizeFragment",
    summary="Contextualizar fragmento",
    description=(
        "Genera un contexto breve que sitúa un fragmento dentro de su documento, "
        "para construir una representación contextualizada (Contextual Retrieval)."
    ),
    responses=_response,
)
