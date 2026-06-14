from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.controllers.user_interactions.document_summary_controller.document_summary_controller_interface import (
    DocumentSummaryControllerInterface,
)
from app.api.openapi.common import default_error_responses
from app.api.sse import sse_response
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_document_summary_service
from app.application.services.user_interactions.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.user_interactions.document_summary.document_summary_response import DocumentSummaryResponse

from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class DocumentSummaryController(DocumentSummaryControllerInterface):
    async def execute_document_summary(
            self,
            document_summary_request: DocumentSummaryRequest,
            document_summary_service: DocumentSummaryServiceInterface = Depends(get_document_summary_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> DocumentSummaryResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DOCUMENT_SUMMARY}),
        )

        return await document_summary_service.execute_document_summary(
            document_summary_request=document_summary_request,
            authenticated_user=authenticated_user,
        )

    async def execute_document_summary_stream(
            self,
            document_summary_request: DocumentSummaryRequest,
            document_summary_service: DocumentSummaryServiceInterface = Depends(get_document_summary_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DOCUMENT_SUMMARY}),
        )

        return sse_response(
            document_summary_service.execute_document_summary_stream(
                document_summary_request=document_summary_request,
                authenticated_user=authenticated_user,
            )
        )


router = APIRouter()
document_summary_controller = DocumentSummaryController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Resumen generado",
        "model": DocumentSummaryResponse,
    },
    **_error,
}
_response_stream = {
    200: {
        "description": "Stream SSE del resumen",
        "content": {"text/event-stream": {}},
    },
    **_error,
}

router.add_api_route(
    "",
    document_summary_controller.execute_document_summary,
    methods=["POST"],
    response_model=DocumentSummaryResponse,
    operation_id="executeDocumentSummary",
    summary="Generar resumen de documento",
    description="Ejecuta el pipeline de resumen sobre los fragmentos del documento.",
    responses=_response,
)

router.add_api_route(
    "/stream",
    document_summary_controller.execute_document_summary_stream,
    methods=["POST"],
    response_class=StreamingResponse,
    operation_id="executeDocumentSummaryStream",
    summary="Generar resumen de documento (SSE)",
    description=(
        "Server-Sent Events: JSON lines con prefijo `data: `. "
        "Tipos de evento: `progress`, `delta`, `complete`, `error` (campo discriminador `type`). "
        "El evento `complete` incluye el resumen completo y los fragmentos de contexto utilizados."
    ),
    responses=_response_stream,
)
