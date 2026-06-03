from fastapi import APIRouter, Depends

from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.decision_brief_service.decision_brief_service import get_decision_brief_service
from app.application.services.decision_brief_service.interfaces.decision_brief_service_interface import (
    DecisionBriefServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.decision_brief.decision_brief_request import DecisionBriefGenerateRequest
from app.domain.dtos.decision_brief.decision_brief_response import DecisionBriefGenerateResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class DecisionBriefController:
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


router = APIRouter()
decision_brief_controller = DecisionBriefController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Brief de decisión generado exitosamente",
        "model": DecisionBriefGenerateResponse,
    },
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
        "En modo `direct` analiza solo el texto provisto por el usuario. "
        "En modo `rag` recupera fragmentos relevantes de los documentos del usuario como contexto adicional. "
        "El campo `messages` actúa como historial: el último mensaje debe ser `human` con el "
        "problema a analizar o la instrucción de refinamiento."
    ),
    responses=_response,
)
