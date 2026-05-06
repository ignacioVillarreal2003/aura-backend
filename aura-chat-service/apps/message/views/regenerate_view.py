import logging

from asgiref.sync import sync_to_async
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.message.chat_ai_reply_lock import release, try_acquire
from apps.message.exceptions import ChatAiReplyInProgressException, LLMServiceException
from apps.message.serializers.response import AssistantBlockSerializer, AssistantErrorSerializer
from apps.message.services.message_service import broadcast_chat_ai_lock_change, message_service
from core.openapi.common import standard_error_responses

logger = logging.getLogger(__name__)


class RegenerateResponseView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="Regenerate last AI response",
        description="Deletes the last AI message and requests a new response from the LLM using the same conversation context.",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={
            200: None,
            **standard_error_responses(401, 403, 404, 409, 502, 503),
        },
    )
    async def post(self, request: Request, chat_id: int) -> Response:
        if not await sync_to_async(try_acquire)(chat_id):
            raise ChatAiReplyInProgressException()

        await sync_to_async(broadcast_chat_ai_lock_change)(chat_id, True)
        assistant = None
        assistant_error = None
        try:
            await sync_to_async(message_service.delete_last_ai_message)(request.user, chat_id)

            try:
                turn = await message_service.run_document_question(request.user, chat_id)
                assistant = {
                    "question": turn.question,
                    "answer": turn.answer,
                    "fragments": turn.fragments,
                }
            except LLMServiceException as e:
                assistant_error = {"detail": e.detail}
            except Exception:
                logger.exception(
                    "Unexpected error regenerating AI response.",
                    extra={"chat_id": chat_id, "user_id": request.user.id},
                )
                assistant_error = {"detail": "AI service encountered an unexpected error."}
        finally:
            await sync_to_async(release)(chat_id)
            await sync_to_async(broadcast_chat_ai_lock_change)(chat_id, False)

        return Response(
            {"assistant": assistant, "assistant_error": assistant_error},
            status=status.HTTP_200_OK,
        )
