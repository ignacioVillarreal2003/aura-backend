from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.controllers.user_interactions.report_controller.report_controller_interface import (
    ReportControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit, strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.api.sse import sse_response
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_report_service
from app.application.services.user_interactions.report_service.interfaces.report_service_interface import ReportServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.report.report_request import ReportGenerateRequest
from app.domain.dtos.user_interactions.report.report_response import ReportGenerateResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class ReportController(ReportControllerInterface):
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

    async def generate_stream(
            self,
            report_request: ReportGenerateRequest,
            report_service: ReportServiceInterface = Depends(get_report_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_REPORT_GENERATE}),
        )

        return sse_response(
            report_service.generate_stream(
                request=report_request,
                authenticated_user=authenticated_user,
            )
        )


router = APIRouter()
report_controller = ReportController()

_error = default_error_responses(include_400=True, include_502=True, include_503=True)
_response = {
    200: {"description": "Informe generado exitosamente", "model": ReportGenerateResponse},
    **_error,
}
_response_stream = {
    200: {"description": "Stream SSE de la generación", "content": {"text/event-stream": {}}},
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
        "En modo `rag` recupera fragmentos de los documentos del usuario como contexto adicional."
    ),
    responses=_response,
)

router.add_api_route(
    "/stream",
    report_controller.generate_stream,
    methods=["POST"],
    response_class=StreamingResponse,
    operation_id="generateReportStream",
    summary="Generar informe estandarizado (SSE)",
    description=(
        "Server-Sent Events: JSON lines con prefijo `data: `. "
        "Tipos de evento: `progress`, `complete`, `error` (campo discriminador `type`)."
    ),
    responses=_response_stream,
)
