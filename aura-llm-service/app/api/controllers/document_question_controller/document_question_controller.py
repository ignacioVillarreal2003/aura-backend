from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.dependencies.idempotency import optional_idempotency_key
from app.api.dependencies.rate_limiter import default_rate_limit, strict_rate_limit
from app.api.controllers.document_question_controller.document_question_controller_interface import (
    DocumentQuestionControllerInterface
)
from app.api.openapi.common import default_error_responses
from app.application.services.document_question_service.document_question_service import get_document_question_service
from app.application.services.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question.document_question_response import DocumentQuestionResponse
from app.domain.dtos.document_question.document_question_stream_events import (
    DocumentQuestionStreamEvent,
)
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class DocumentQuestionController(DocumentQuestionControllerInterface):
    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            document_question_service: DocumentQuestionServiceInterface = Depends(get_document_question_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _idemp: None = Depends(optional_idempotency_key),
            _rl: None = Depends(default_rate_limit),
    ) -> DocumentQuestionResponse:
        return await document_question_service.execute_document_question(
            document_question_request=document_question_request,
            authenticated_user=authenticated_user
        )

    async def execute_document_question_stream(
            self,
            document_question_request: DocumentQuestionRequest,
            document_question_service: DocumentQuestionServiceInterface = Depends(get_document_question_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> StreamingResponse:
        async def sse_bytes() -> AsyncIterator[bytes]:
            async for event in document_question_service.execute_document_question_stream(
                    document_question_request=document_question_request,
                    authenticated_user=authenticated_user,
            ):
                line = _format_sse_event(event)
                yield line.encode("utf-8")

        return StreamingResponse(
            sse_bytes(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )


def _format_sse_event(event: DocumentQuestionStreamEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"


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
