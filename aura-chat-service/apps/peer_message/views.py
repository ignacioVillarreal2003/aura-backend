import logging

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.peer_message.serializers.request import (
    CreatePeerMessageRequest,
    UpdatePeerMessageRequest,
)
from apps.peer_message.serializers.response import PeerMessageResponse
from apps.peer_message.services.peer_message_service import peer_message_service
from core.openapi.common import standard_error_responses
from core.pagination.pagination import MessageCursorPagination

logger = logging.getLogger(__name__)

_CHAT_ID_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="Chat ID",
)
_MESSAGE_ID_PARAM = OpenApiParameter(
    name="message_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="Peer message ID",
)


class PeerMessageListView(APIView):
    @extend_schema(
        tags=["Peer Chat"],
        summary="List peer messages",
        description=(
                "Human-to-human messages of the chat (no AI), newest first, cursor paginated. "
                "Requires active membership in the chat."
        ),
        parameters=[_CHAT_ID_PARAM],
        responses={200: PeerMessageResponse(many=True), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int) -> Response:
        messages = peer_message_service.list(user=request.user, chat_id=chat_id)
        paginator = MessageCursorPagination()
        page = paginator.paginate_queryset(messages, request)
        return paginator.get_paginated_response(PeerMessageResponse(page, many=True).data)

    @extend_schema(
        tags=["Peer Chat"],
        summary="Send peer message",
        description="Sends a human-to-human message. Any active member (including readers) can send.",
        parameters=[_CHAT_ID_PARAM],
        request=CreatePeerMessageRequest,
        responses={201: PeerMessageResponse, **standard_error_responses(400, 401, 403, 404)},
    )
    def post(self, request: Request, chat_id: int) -> Response:
        serializer = CreatePeerMessageRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        msg = peer_message_service.create(
            user=request.user, chat_id=chat_id, text=serializer.validated_data["message"]
        )
        return Response(PeerMessageResponse(msg).data, status=status.HTTP_201_CREATED)


class PeerMessageDetailView(APIView):
    @extend_schema(
        tags=["Peer Chat"],
        summary="Get peer message",
        parameters=[_CHAT_ID_PARAM, _MESSAGE_ID_PARAM],
        responses={200: PeerMessageResponse, **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int, message_id: int) -> Response:
        msg = peer_message_service.get(
            user=request.user, chat_id=chat_id, message_id=message_id
        )
        return Response(PeerMessageResponse(msg).data)

    @extend_schema(
        tags=["Peer Chat"],
        summary="Edit peer message",
        description="Edits a message. Only the author can edit their own message.",
        parameters=[_CHAT_ID_PARAM, _MESSAGE_ID_PARAM],
        request=UpdatePeerMessageRequest,
        responses={200: PeerMessageResponse, **standard_error_responses(400, 401, 403, 404)},
    )
    def patch(self, request: Request, chat_id: int, message_id: int) -> Response:
        serializer = UpdatePeerMessageRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        msg = peer_message_service.update(
            user=request.user,
            chat_id=chat_id,
            message_id=message_id,
            text=serializer.validated_data["message"],
        )
        return Response(PeerMessageResponse(msg).data)

    @extend_schema(
        tags=["Peer Chat"],
        summary="Delete peer message",
        description="Soft-deletes a message. The author or the chat owner can delete.",
        parameters=[_CHAT_ID_PARAM, _MESSAGE_ID_PARAM],
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, chat_id: int, message_id: int) -> Response:
        peer_message_service.delete(
            user=request.user, chat_id=chat_id, message_id=message_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
