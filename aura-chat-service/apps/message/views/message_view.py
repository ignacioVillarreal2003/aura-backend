from asgiref.sync import async_to_sync
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.message.exceptions import LLMServiceException, TranscriptionException
from apps.message.serializers.request import SendMessageRequest
from apps.message.serializers.response import (
    MessageResponse,
    SendMessagePostResponseSerializer,
)
from apps.message.services.message_service import message_service
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
        responses={201: SendMessagePostResponseSerializer, **standard_error_responses(400, 401, 403, 404, 502)},
    )
    def post(self, request: Request, chat_id: int) -> Response:
        serializer = SendMessageRequest(data=request.data)
        serializer.is_valid(raise_exception=True)

        transcript = None
        if "audio" in serializer.validated_data:
            transcript = message_service.transcribe_audio(serializer.validated_data["audio"])
            text = transcript
        else:
            text = serializer.validated_data["message"]

        msg = message_service.send_message(
            user=request.user,
            chat_id=chat_id,
            text=text,
        )

        assistant = None
        assistant_error = None
        try:
            turn = async_to_sync(message_service.run_document_question)(
                request.user, chat_id
            )
            assistant = {
                "question": turn.question,
                "answer": turn.answer,
                "fragments": turn.fragments,
            }
        except LLMServiceException as e:
            assistant_error = {"detail": e.detail}

        body = {
            "message": MessageResponse(msg).data,
            "transcript": transcript,
            "assistant": assistant,
            "assistant_error": assistant_error,
        }
        return Response(body, status=status.HTTP_201_CREATED)
