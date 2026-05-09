import logging

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.message.serializers.response import MessageResponse
from apps.message.services.bookmark_service import bookmark_service
from core.openapi.common import standard_error_responses
from core.pagination.pagination import MessageCursorPagination

logger = logging.getLogger(__name__)

_PATH_PARAMS = [
    OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
    OpenApiParameter(name="message_id", type=int, location=OpenApiParameter.PATH, required=True),
]


class BookmarkView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="Bookmark message",
        description="Adds a **personal bookmark** on this message for the authenticated user.",
        request=None,
        parameters=_PATH_PARAMS,
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    def post(self, request: Request, chat_id: int, message_id: int) -> Response:
        bookmark_service.bookmark(user=request.user, chat_id=chat_id, message_id=message_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Messages"],
        summary="Remove bookmark",
        description="Removes the user's bookmark on this message (if present).",
        request=None,
        parameters=_PATH_PARAMS,
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, chat_id: int, message_id: int) -> Response:
        bookmark_service.unbookmark(user=request.user, chat_id=chat_id, message_id=message_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BookmarkedMessageListView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="List bookmarked messages",
        description=(
            "Returns messages the user bookmarked **in this chat**, with **cursor pagination** (same style as "
            "the main message list)."
        ),
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={200: MessageResponse(many=True), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int) -> Response:
        messages = bookmark_service.list_bookmarked(user=request.user, chat_id=chat_id)
        paginator = MessageCursorPagination()
        page = paginator.paginate_queryset(messages, request)
        return paginator.get_paginated_response(MessageResponse(page, many=True).data)
