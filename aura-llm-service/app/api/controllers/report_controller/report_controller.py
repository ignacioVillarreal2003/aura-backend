from fastapi import APIRouter, Depends

from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.report_service.report_service import get_report_service
from app.application.services.report_service.interfaces.report_service_interface import ReportServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.report.report_request import ReportGenerateRequest
from app.domain.dtos.report.report_response import ReportGenerateResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class ReportController:
    async def generate(
            self,
            report_request: ReportGenerateRequest,
            report_service: ReportServiceInterface = Depends(get_report_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> ReportGenerateResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_REPORT_GENERATE}),
        )
        return await report_service.generate(
            request=report_request,
            authenticated_user=authenticated_user,
        )


router = APIRouter()
report_controller = ReportController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Informe generado exitosamente",
        "model": ReportGenerateResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    report_controller.generate,
    methods=["POST"],
    response_model=ReportGenerateResponse,
    operation_id="generateReport",
    summary="Generar informe estandarizado",
    description=(
        "Genera un informe militar estandarizado (SITREP, INTSUM u OPORD) a partir del input del usuario. "
        "En modo `direct` usa solo el contenido provisto. "
        "En modo `rag` recupera fragmentos de los documentos del usuario como contexto adicional. "
        "El campo `messages` actúa como historial de conversación: el último mensaje debe ser `human` "
        "con el contenido operacional o instrucción de retoque. "
        "Las respuestas previas del asistente se incluyen como mensajes `assistant` para refinamientos iterativos."
    ),
    responses=_response,
)
