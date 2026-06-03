from fastapi import APIRouter, Depends

from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.timeline_service.timeline_service import get_timeline_service
from app.application.services.timeline_service.interfaces.timeline_service_interface import TimelineServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.timeline.timeline_request import TimelineGenerateRequest
from app.domain.dtos.timeline.timeline_response import TimelineGenerateResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class TimelineController:
    async def generate(
            self,
            timeline_request: TimelineGenerateRequest,
            timeline_service: TimelineServiceInterface = Depends(get_timeline_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> TimelineGenerateResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_TIMELINE_GENERATE}),
        )
        return await timeline_service.generate(
            request=timeline_request,
            authenticated_user=authenticated_user,
        )


router = APIRouter()
timeline_controller = TimelineController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Línea de tiempo generada exitosamente",
        "model": TimelineGenerateResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    timeline_controller.generate,
    methods=["POST"],
    response_model=TimelineGenerateResponse,
    operation_id="generateTimeline",
    summary="Generar línea de tiempo desde un relato",
    description=(
        "Reconstruye una cronología de eventos a partir de un relato, parte o informe. "
        "En modo `direct` analiza solo el texto provisto por el usuario. "
        "En modo `rag` recupera fragmentos relevantes de los documentos del usuario como contexto adicional. "
        "El campo `messages` actúa como historial: el último mensaje debe ser `human` con el "
        "texto a analizar o la instrucción de refinamiento."
    ),
    responses=_response,
)
