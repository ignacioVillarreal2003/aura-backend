from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.controllers.user_interactions.document_action_controller.document_action_controller_interface import (
    DocumentActionControllerInterface,
)
from app.api.openapi.common import default_error_responses
from app.api.sse import sse_response
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_document_action_service
from app.application.services.user_interactions.document_action_service.interfaces.document_action_service_interface import (
    DocumentActionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.user_interactions.document_action.document_action_response import DocumentActionResponse

from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class DocumentActionController(DocumentActionControllerInterface):
    async def execute_document_action(
            self,
            document_action_request: DocumentActionRequest,
            document_action_service: DocumentActionServiceInterface = Depends(get_document_action_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> DocumentActionResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DOCUMENT_ACTION}),
        )
        return await document_action_service.execute_document_action(
            document_action_request=document_action_request,
            authenticated_user=authenticated_user,
        )

    async def execute_document_action_stream(
            self,
            document_action_request: DocumentActionRequest,
            document_action_service: DocumentActionServiceInterface = Depends(get_document_action_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DOCUMENT_ACTION}),
        )

        return sse_response(
            document_action_service.execute_document_action_stream(
                document_action_request=document_action_request,
                authenticated_user=authenticated_user,
            )
        )


router = APIRouter()
document_action_controller = DocumentActionController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Acción ejecutada",
        "model": DocumentActionResponse,
    },
    **_error,
}
_response_stream = {
    200: {
        "description": "Stream SSE de la acción",
        "content": {"text/event-stream": {}},
    },
    **_error,
}

router.add_api_route(
    "",
    document_action_controller.execute_document_action,
    methods=["POST"],
    response_model=DocumentActionResponse,
    operation_id="executeDocumentAction",
    summary="Ejecutar acción sobre documento",
    description="Ejecuta una acción estructurada sobre los fragmentos del documento usando el LLM.",
    responses=_response,
)

router.add_api_route(
    "/stream",
    document_action_controller.execute_document_action_stream,
    methods=["POST"],
    response_class=StreamingResponse,
    operation_id="executeDocumentActionStream",
    summary="Ejecutar acción sobre documento (SSE)",
    description=(
        "Server-Sent Events: JSON lines con prefijo `data: `. "
        "Tipos de evento: `progress`, `delta`, `complete`, `error` (campo discriminador `type`). "
        "Los eventos `progress` indican la etapa actual del pipeline. "
        "Los eventos `delta` contienen fragmentos de texto generado en tiempo real. "
        "El evento `complete` incluye la respuesta completa y los fragmentos utilizados."
    ),
    responses=_response_stream,
)
