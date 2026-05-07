import logging

from asgiref.sync import async_to_sync, sync_to_async
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

from apps.chat.repositories.chat_repository import chat_repository
from apps.message.chat_ai_reply_lock import release, try_acquire
from apps.message.exceptions import (
    ChatAiReplyInProgressException,
    LLMServiceException,
    TranscriptionException,
)
from apps.message.serializers.request import SendMessageRequest
from apps.message.serializers.response import (
    MessageResponse,
    SendMessagePostResponseSerializer,
)
from apps.message.services.message_service import (
    broadcast_chat_ai_lock_change,
    message_service,
)
from core.openapi.common import standard_error_responses
from core.pagination.pagination import MessageCursorPagination


class MessageListView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="List messages",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={200: MessageResponse(many=True), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int) -> Response:
        messages = message_service.get_messages(user=request.user, chat_id=chat_id)
        paginator = MessageCursorPagination()
        page = paginator.paginate_queryset(messages, request)
        return paginator.get_paginated_response(
            MessageResponse(page, many=True).data
        )

    @extend_schema(
        tags=["Messages"],
        summary="Send message",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        request={"multipart/form-data": SendMessageRequest, "application/json": SendMessageRequest},
        responses={
            201: SendMessagePostResponseSerializer,
            **standard_error_responses(400, 401, 403, 404, 409, 502, 503),
        },
    )
    def post(self, request: Request, chat_id: int) -> Response:
        return async_to_sync(self._post_async)(request, chat_id)

    async def _post_async(self, request: Request, chat_id: int) -> Response:
        serializer = SendMessageRequest(data=request.data)
        serializer.is_valid(raise_exception=True)

        transcript = None
        if "audio" in serializer.validated_data:
            transcript = await sync_to_async(message_service.transcribe_audio)(
                serializer.validated_data["audio"]
            )
            text = transcript
        else:
            text = serializer.validated_data["message"]

        chat_obj = await sync_to_async(chat_repository.get_by_id)(chat_id)
        is_ephemeral = chat_obj is not None and chat_obj.is_ephemeral

        if not await sync_to_async(try_acquire)(chat_id):
            raise ChatAiReplyInProgressException()

        await sync_to_async(broadcast_chat_ai_lock_change)(chat_id, True)
        assistant = None
        assistant_error = None
        msg = None
        try:
            if is_ephemeral:
                msg = await sync_to_async(message_service.send_ephemeral_message)(
                    user=request.user,
                    chat_id=chat_id,
                    text=text,
                )
                try:
                    turn = await message_service.run_ephemeral_document_question(
                        request.user, chat_id, text
                    )
                    assistant = {
                        "question": turn.question,
                        "answer": turn.answer,
                        "fragments": turn.fragments,
                    }
                except LLMServiceException as e:
                    assistant_error = {"detail": e.detail}
                except Exception:
                    logger.exception(
                        "Unexpected error running ephemeral document question.",
                        extra={"chat_id": chat_id, "user_id": request.user.id},
                    )
                    assistant_error = {"detail": "AI service encountered an unexpected error."}
            else:
                msg = await sync_to_async(message_service.send_message)(
                    user=request.user,
                    chat_id=chat_id,
                    text=text,
                )
                try:
                    turn = await message_service.run_document_question(
                        request.user, chat_id
                    )
                    assistant = {
                        "question": turn.question,
                        "answer": turn.answer,
                        "fragments": turn.fragments,
                    }
                except LLMServiceException as e:
                    assistant_error = {"detail": e.detail}
                except Exception:
                    logger.exception(
                        "Unexpected error running document question.",
                        extra={"chat_id": chat_id, "user_id": request.user.id},
                    )
                    assistant_error = {"detail": "AI service encountered an unexpected error."}
        finally:
            await sync_to_async(release)(chat_id)
            await sync_to_async(broadcast_chat_ai_lock_change)(chat_id, False)

        body = {
            "message": MessageResponse(msg).data,
            "transcript": transcript,
            "assistant": assistant,
            "assistant_error": assistant_error,
        }
        return Response(body, status=status.HTTP_201_CREATED)
