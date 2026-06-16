from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.controllers.user_interactions.decision_brief_controller.decision_brief_controller_interface import (
    DecisionBriefControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit, strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.api.sse import sse_response
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_decision_brief_service
from app.application.services.user_interactions.decision_brief_service.interfaces.decision_brief_service_interface import (
    DecisionBriefServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.decision_brief.decision_brief_request import DecisionBriefGenerateRequest
from app.domain.dtos.user_interactions.decision_brief.decision_brief_response import DecisionBriefGenerateResponse

from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class DecisionBriefController(DecisionBriefControllerInterface):
    async def generate(
            self,
            decision_brief_request: DecisionBriefGenerateRequest,
            decision_brief_service: DecisionBriefServiceInterface = Depends(get_decision_brief_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> DecisionBriefGenerateResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DECISION_BRIEF_GENERATE}),
        )

        return await decision_brief_service.generate(
            request=decision_brief_request,
            authenticated_user=authenticated_user,
        )

    async def generate_stream(
            self,
            decision_brief_request: DecisionBriefGenerateRequest,
            decision_brief_service: DecisionBriefServiceInterface = Depends(get_decision_brief_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DECISION_BRIEF_GENERATE}),
        )

        return sse_response(
            decision_brief_service.generate_stream(
                request=decision_brief_request,
                authenticated_user=authenticated_user,
            )
        )


router = APIRouter()
decision_brief_controller = DecisionBriefController()

_error = default_error_responses(include_400=True, include_502=True, include_503=True)
_response = {
    200: {"description": "Brief de decisión generado exitosamente", "model": DecisionBriefGenerateResponse},
    **_error,
}
_response_stream = {
    200: {"description": "Stream SSE de la generación", "content": {"text/event-stream": {}}},
    **_error,
}

router.add_api_route(
    "",
    decision_brief_controller.generate,
    methods=["POST"],
    response_model=DecisionBriefGenerateResponse,
    operation_id="generateDecisionBrief",
    summary="Generar brief de decisión ejecutivo",
    description=(
        "Genera un documento ejecutivo de decisión (problema, opciones, riesgos y recomendación) para jefaturas. "
        "En modo `direct` analiza solo el texto provisto. "
        "En modo `rag` recupera fragmentos relevantes de los documentos del usuario."
    ),
    responses=_response,
)

router.add_api_route(
    "/stream",
    decision_brief_controller.generate_stream,
    methods=["POST"],
    response_class=StreamingResponse,
    operation_id="generateDecisionBriefStream",
    summary="Generar brief de decisión (SSE)",
    description=(
        "Server-Sent Events: JSON lines con prefijo `data: `. "
        "Tipos de evento: `progress`, `complete`, `error` (campo discriminador `type`)."
    ),
    responses=_response_stream,
)
