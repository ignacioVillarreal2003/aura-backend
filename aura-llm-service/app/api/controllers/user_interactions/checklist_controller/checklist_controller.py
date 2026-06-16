from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.controllers.user_interactions.checklist_controller.checklist_controller_interface import (
    ChecklistControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit, strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.api.sse import sse_response
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_checklist_service
from app.application.services.user_interactions.checklist_service.interfaces.checklist_service_interface import (
    ChecklistServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.checklist.checklist_request import ChecklistGenerateRequest
from app.domain.dtos.user_interactions.checklist.checklist_response import ChecklistGenerateResponse

from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class ChecklistController(ChecklistControllerInterface):
    async def generate(
            self,
            checklist_request: ChecklistGenerateRequest,
            checklist_service: ChecklistServiceInterface = Depends(get_checklist_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> ChecklistGenerateResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_CHECKLIST_GENERATE}),
        )

        return await checklist_service.generate(
            request=checklist_request,
            authenticated_user=authenticated_user,
        )

    async def generate_stream(
            self,
            checklist_request: ChecklistGenerateRequest,
            checklist_service: ChecklistServiceInterface = Depends(get_checklist_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_CHECKLIST_GENERATE}),
        )

        return sse_response(
            checklist_service.generate_stream(
                request=checklist_request,
                authenticated_user=authenticated_user,
            )
        )


router = APIRouter()
checklist_controller = ChecklistController()

_error = default_error_responses(include_400=True, include_502=True, include_503=True)
_response = {
    200: {"description": "Checklist generada exitosamente", "model": ChecklistGenerateResponse},
    **_error,
}
_response_stream = {
    200: {"description": "Stream SSE de la generación", "content": {"text/event-stream": {}}},
    **_error,
}

router.add_api_route(
    "",
    checklist_controller.generate,
    methods=["POST"],
    response_model=ChecklistGenerateResponse,
    operation_id="generateChecklist",
    summary="Generar checklist desde procedimiento",
    description=(
        "Extrae y estructura los pasos de un procedimiento operacional en una checklist interactiva. "
        "En modo `direct` analiza solo el texto provisto por el usuario. "
        "En modo `rag` recupera fragmentos relevantes de los documentos del usuario como contexto adicional."
    ),
    responses=_response,
)

router.add_api_route(
    "/stream",
    checklist_controller.generate_stream,
    methods=["POST"],
    response_class=StreamingResponse,
    operation_id="generateChecklistStream",
    summary="Generar checklist (SSE)",
    description=(
        "Server-Sent Events: JSON lines con prefijo `data: `. "
        "Tipos de evento: `progress`, `complete`, `error` (campo discriminador `type`)."
    ),
    responses=_response_stream,
)
