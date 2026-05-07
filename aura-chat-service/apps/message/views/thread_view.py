import logging

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.message.serializers.request import SendThreadReplyRequest
from apps.message.serializers.response import ThreadReplyResponse
from apps.message.services.thread_service import thread_service
from core.authorization import AccessControl
from core.authorization.permissions import ADD_THREAD_REPLY, LIST_THREAD_REPLIES
from core.openapi.common import standard_error_responses

logger = logging.getLogger(__name__)

_PATH_PARAMS = [
    OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
    OpenApiParameter(name="message_id", type=int, location=OpenApiParameter.PATH, required=True),
]


class ThreadView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="List thread replies",
        description=(
            "Returns all thread replies for the given **parent** message id in chronological order. "
            "The parent must belong to `chat_id` and the caller must have access to the chat."
        ),
        parameters=_PATH_PARAMS,
        responses={200: ThreadReplyResponse(many=True), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int, message_id: int) -> Response:
        AccessControl.require_permissions(request.user, frozenset({LIST_THREAD_REPLIES}))
        replies = thread_service.get_thread(
            user=request.user, chat_id=chat_id, message_id=message_id
        )
        return Response(ThreadReplyResponse(replies, many=True).data)

    @extend_schema(
        tags=["Messages"],
        summary="Add thread reply",
        description=(
            "Creates a **MessageThreadReply** under the parent message. Used for side discussions without "
            "cluttering the main timeline."
        ),
        parameters=_PATH_PARAMS,
        request=SendThreadReplyRequest,
        responses={201: ThreadReplyResponse, **standard_error_responses(400, 401, 403, 404)},
    )
    def post(self, request: Request, chat_id: int, message_id: int) -> Response:
        AccessControl.require_permissions(request.user, frozenset({ADD_THREAD_REPLY}))
        serializer = SendThreadReplyRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        reply = thread_service.add_reply(
            user=request.user,
            chat_id=chat_id,
            message_id=message_id,
            message_text=serializer.validated_data["message"],
        )
        return Response(ThreadReplyResponse(reply).data, status=status.HTTP_201_CREATED)
