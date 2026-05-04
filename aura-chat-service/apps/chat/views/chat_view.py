from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.chat.serializers.request import CreateChatRequest, UpdateChatRequest
from apps.chat.serializers.response import ChatListResponse, ChatResponse
from apps.chat.services.chat_service import chat_service
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination


@extend_schema_view(
    list=extend_schema(
        tags=["Chats"],
        summary="List chats",
        responses={200: ChatListResponse(many=True), **standard_error_responses(401)},
    ),
    create=extend_schema(
        tags=["Chats"],
        summary="Create chat",
        request=CreateChatRequest,
        responses={201: ChatResponse, **standard_error_responses(400, 401)},
    ),
    retrieve=extend_schema(
        tags=["Chats"],
        summary="Get chat",
        responses={200: ChatResponse, **standard_error_responses(401, 403, 404)},
    ),
    partial_update=extend_schema(
        tags=["Chats"],
        summary="Update chat",
        request=UpdateChatRequest,
        responses={200: ChatResponse, **standard_error_responses(400, 401, 403, 404)},
    ),
    destroy=extend_schema(
        tags=["Chats"],
        summary="Delete chat",
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    ),
    my_chats=extend_schema(
        tags=["Chats"],
        summary="List chats created by me",
        responses={200: ChatListResponse(many=True), **standard_error_responses(401)},
    ),
)
class ChatViewSet(ViewSet):
    def create(self, request: Request) -> Response:
        serializer = CreateChatRequest(data=request.data)
        serializer.is_valid(raise_exception=True)

        chat = chat_service.create_chat(
            user=request.user,
            **serializer.validated_data,
        )
        return Response(
            ChatResponse(chat).data,
            status=status.HTTP_201_CREATED,
        )

    def list(self, request: Request) -> Response:
        chats = chat_service.list_chats(user=request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(chats, request)
        return paginator.get_paginated_response(
            ChatListResponse(page, many=True).data
        )

    def retrieve(self, request: Request, pk=None) -> Response:
        chat = chat_service.get_chat(user=request.user, chat_id=int(pk))
        return Response(ChatResponse(chat).data)

    def partial_update(self, request: Request, pk=None) -> Response:
        serializer = UpdateChatRequest(data=request.data)
        serializer.is_valid(raise_exception=True)

        chat = chat_service.update_chat(
            user=request.user,
            chat_id=int(pk),
            **serializer.validated_data,
        )
        return Response(ChatResponse(chat).data)

    def destroy(self, request: Request, pk=None) -> Response:
        chat_service.delete_chat(user=request.user, chat_id=int(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="me")
    def my_chats(self, request: Request) -> Response:
        chats = chat_service.list_own_chats(user=request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(chats, request)
        return paginator.get_paginated_response(
            ChatListResponse(page, many=True).data
        )
