from fastapi import APIRouter, Depends

from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.checklist_service.checklist_service import get_checklist_service
from app.application.services.checklist_service.interfaces.checklist_service_interface import ChecklistServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.checklist.checklist_request import ChecklistGenerateRequest
from app.domain.dtos.checklist.checklist_response import ChecklistGenerateResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class ChecklistController:
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


router = APIRouter()
checklist_controller = ChecklistController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Checklist generada exitosamente",
        "model": ChecklistGenerateResponse,
    },
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
        "En modo `rag` recupera fragmentos relevantes de los documentos del usuario como contexto adicional. "
        "El campo `messages` actúa como historial: el último mensaje debe ser `human` con el texto del "
        "procedimiento o instrucción de refinamiento."
    ),
    responses=_response,
)
