from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.dependencies.rate_limiter import default_rate_limit, strict_rate_limit
from app.api.controllers.user_interactions.document_question_controller.document_question_controller_interface import (
    DocumentQuestionControllerInterface,
)
from app.api.openapi.common import default_error_responses
from app.api.sse import sse_response
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_document_question_service
from app.application.services.user_interactions.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.user_interactions.document_question.document_question_response import DocumentQuestionResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class DocumentQuestionController(DocumentQuestionControllerInterface):
    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            document_question_service: DocumentQuestionServiceInterface = Depends(get_document_question_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> DocumentQuestionResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DOCUMENT_QUESTION}),
        )

        return await document_question_service.execute_document_question(
            document_question_request=document_question_request,
            authenticated_user=authenticated_user,
        )

    async def execute_document_question_stream(
            self,
            document_question_request: DocumentQuestionRequest,
            document_question_service: DocumentQuestionServiceInterface = Depends(get_document_question_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> StreamingResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DOCUMENT_QUESTION}),
        )

        return sse_response(
            document_question_service.execute_document_question_stream(
                document_question_request=document_question_request,
                authenticated_user=authenticated_user,
            )
        )


router = APIRouter()
document_question_controller = DocumentQuestionController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Respuesta a la pregunta",
        "model": DocumentQuestionResponse,
    },
    **_error,
}
_response_stream = {
    200: {
        "description": "Stream SSE de la respuesta",
        "content": {"text/event-stream": {}},
    },
    **_error,
}

router.add_api_route(
    "",
    document_question_controller.execute_document_question,
    methods=["POST"],
    response_model=DocumentQuestionResponse,
    operation_id="executeDocumentQuestion",
    summary="Responder pregunta sobre documentos",
    description="Ejecuta RAG sobre los documentos del usuario y devuelve la respuesta.",
    responses=_response,
)

router.add_api_route(
    "/stream",
    document_question_controller.execute_document_question_stream,
    methods=["POST"],
    response_class=StreamingResponse,
    operation_id="executeDocumentQuestionStream",
    summary="Responder pregunta sobre documentos (SSE)",
    description=(
        "Server-Sent Events: JSON lines con prefijo `data: `. "
        "Tipos de evento: `meta`, `delta`, `complete`, `error` (campo discriminador `type`)."
    ),
    responses=_response_stream,
)
