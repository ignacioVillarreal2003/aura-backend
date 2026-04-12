import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.controllers.general.document_question_controller.interfaces.document_question_controller_interface import (
    DocumentQuestionControllerInterface
)
from app.application.services.general.document_question_service.document_question_service import get_document_question_service
from app.application.services.general.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.general.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.general.document_question.document_question_response import DocumentQuestionResponse
from app.domain.dtos.general.document_question.document_question_stream_events import (
    DocumentQuestionStreamEvent,
)
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class DocumentQuestionController(DocumentQuestionControllerInterface):
    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            document_question_service: DocumentQuestionServiceInterface = Depends(get_document_question_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> DocumentQuestionResponse:
        logger.info(
            "Handling document question request",
            extra={
                "user_id": authenticated_user.id
            }
        )

        document_question_response = await document_question_service.execute_document_question(
            document_question_request=document_question_request,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Document question completed successfully",
            extra={
                "user_id": authenticated_user.id
            }
        )

        return document_question_response

    async def execute_document_question_stream(
            self,
            document_question_request: DocumentQuestionRequest,
            document_question_service: DocumentQuestionServiceInterface = Depends(get_document_question_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> StreamingResponse:
        logger.info(
            "Handling document question stream request",
            extra={"user_id": authenticated_user.id},
        )

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

router.post(
    "",
    response_model=DocumentQuestionResponse,
)(document_question_controller.execute_document_question)

router.post(
    "/stream",
    summary="Stream document question answer (SSE)",
    description=(
        "Server-Sent Events: JSON lines prefixed with `data: `. "
        "Event types are `meta`, `delta`, `complete`, and `error` (discriminator field `type`)."
    ),
)(document_question_controller.execute_document_question_stream)
