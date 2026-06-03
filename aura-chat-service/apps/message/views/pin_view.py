from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.message.serializers.response import PinnedMessageResponse
from apps.message.services.pinned_message_service import pinned_message_service
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination


class PinnedMessageListView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="List pinned messages",
        description=(
                "Lists messages pinned **in this chat** (page-number pagination). Each row includes nested "
                "`message` details for the pinned item."
        ),
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={200: PinnedMessageResponse(many=True), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int) -> Response:
        pins = pinned_message_service.list_pinned(user=request.user, chat_id=chat_id)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(pins, request)
        return paginator.get_paginated_response(PinnedMessageResponse(page, many=True).data)


class PinMessageView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Pin a message",
        description="Creates a **PinnedMessage** so the message appears in the chat's pinned list (moderation/highlight).",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(name="message_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        request=None,
        responses={201: PinnedMessageResponse, **standard_error_responses(401, 403, 404)},
    )
    def post(self, request: Request, chat_id: int, message_id: int) -> Response:
        pin = pinned_message_service.pin_message(
            user=request.user,
            chat_id=chat_id,
            artifact_id=message_id,
        )
        return Response(PinnedMessageResponse(pin).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Messages"],
        summary="Unpin a message",
        description="Removes the pin for this message in the chat (idempotent if already unpinned).",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(name="message_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, chat_id: int, message_id: int) -> Response:
        pinned_message_service.unpin_message(
            user=request.user,
            chat_id=chat_id,
            artifact_id=message_id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
