from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.controllers.user_interactions.timeline_controller.timeline_controller_interface import (
    TimelineControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit, strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.api.sse import sse_response
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_timeline_service
from app.application.services.user_interactions.timeline_service.interfaces.timeline_service_interface import (
    TimelineServiceInterface
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.timeline.timeline_request import TimelineGenerateRequest
from app.domain.dtos.user_interactions.timeline.timeline_response import TimelineGenerateResponse

from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class TimelineController(TimelineControllerInterface):
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

    async def generate_stream(
            self,
            timeline_request: TimelineGenerateRequest,
            timeline_service: TimelineServiceInterface = Depends(get_timeline_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_TIMELINE_GENERATE}),
        )

        return sse_response(
            timeline_service.generate_stream(
                request=timeline_request,
                authenticated_user=authenticated_user,
            )
        )


router = APIRouter()
timeline_controller = TimelineController()

_error = default_error_responses(include_400=True, include_502=True, include_503=True)
_response = {
    200: {"description": "Línea de tiempo generada exitosamente", "model": TimelineGenerateResponse},
    **_error,
}
_response_stream = {
    200: {"description": "Stream SSE de la generación", "content": {"text/event-stream": {}}},
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
        "En modo `direct` analiza solo el texto provisto. "
        "En modo `rag` recupera fragmentos relevantes de los documentos del usuario."
    ),
    responses=_response,
)

router.add_api_route(
    "/stream",
    timeline_controller.generate_stream,
    methods=["POST"],
    response_class=StreamingResponse,
    operation_id="generateTimelineStream",
    summary="Generar línea de tiempo (SSE)",
    description=(
        "Server-Sent Events: JSON lines con prefijo `data: `. "
        "Tipos de evento: `progress`, `complete`, `error` (campo discriminador `type`)."
    ),
    responses=_response_stream,
)
