from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.chat.repositories.chat_repository import ALLOWED_ORDERINGS


def _parse_tags(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    tags = [t.strip() for t in raw.split(",") if t.strip()]
    return tags or None
from apps.chat.serializers.request import BulkChatIdsRequest, CreateChatRequest, MuteChatRequest, UpdateChatRequest
from apps.chat.serializers.response import ChatListResponse, ChatResponse
from apps.chat.services.chat_service import chat_service
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

_ORDERING_ENUM = sorted(ALLOWED_ORDERINGS)

_SEARCH_PARAM = OpenApiParameter(
    name="search",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Filter chats by name (case-insensitive contains).",
)
_ORDERING_PARAM = OpenApiParameter(
    name="ordering",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    enum=_ORDERING_ENUM,
    description="Sort field. Pinned chats always appear first regardless of ordering.",
)
_TAGS_PARAM = OpenApiParameter(
    name="tags",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Comma-separated tag list. Returns chats that contain ALL specified tags (e.g. tags=work,urgent).",
)


@extend_schema_view(
    list=extend_schema(
        tags=["Chats"],
        summary="List chats",
        parameters=[_SEARCH_PARAM, _ORDERING_PARAM, _TAGS_PARAM],
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
        parameters=[_SEARCH_PARAM, _ORDERING_PARAM, _TAGS_PARAM],
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
        return Response(ChatResponse(chat).data, status=status.HTTP_201_CREATED)

    def list(self, request: Request) -> Response:
        search = request.query_params.get("search") or None
        ordering = request.query_params.get("ordering") or None
        if ordering not in ALLOWED_ORDERINGS:
            ordering = None
        tags = _parse_tags(request.query_params.get("tags"))

        chats = chat_service.list_chats(user=request.user, search=search, ordering=ordering, tags=tags)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(chats, request)
        return paginator.get_paginated_response(ChatListResponse(page, many=True).data)

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
        search = request.query_params.get("search") or None
        ordering = request.query_params.get("ordering") or None
        if ordering not in ALLOWED_ORDERINGS:
            ordering = None
        tags = _parse_tags(request.query_params.get("tags"))

        chats = chat_service.list_own_chats(user=request.user, search=search, ordering=ordering, tags=tags)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(chats, request)
        return paginator.get_paginated_response(ChatListResponse(page, many=True).data)

    @extend_schema(
        methods=["POST"],
        tags=["Chats"],
        summary="Pin chat",
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    @extend_schema(
        methods=["DELETE"],
        tags=["Chats"],
        summary="Unpin chat",
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    @action(detail=True, methods=["post", "delete"], url_path="pin")
    def pin(self, request: Request, pk=None) -> Response:
        if request.method == "POST":
            chat_service.pin_chat(user=request.user, chat_id=int(pk))
        else:
            chat_service.unpin_chat(user=request.user, chat_id=int(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Chats"],
        summary="List archived chats",
        parameters=[_SEARCH_PARAM, _ORDERING_PARAM, _TAGS_PARAM],
        responses={200: ChatListResponse(many=True), **standard_error_responses(401)},
    )
    @action(detail=False, methods=["get"], url_path="archived")
    def archived(self, request: Request) -> Response:
        search = request.query_params.get("search") or None
        ordering = request.query_params.get("ordering") or None
        if ordering not in ALLOWED_ORDERINGS:
            ordering = None
        tags = _parse_tags(request.query_params.get("tags"))

        chats = chat_service.list_archived_chats(
            user=request.user, search=search, ordering=ordering, tags=tags
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(chats, request)
        return paginator.get_paginated_response(ChatListResponse(page, many=True).data)

    @extend_schema(
        tags=["Chats"],
        summary="Archive chats",
        description="Archiva uno o varios chats para el usuario autenticado. Los chats archivados dejan de aparecer en el listado principal pero pueden restaurarse.",
        request=BulkChatIdsRequest,
        responses={
            200: OpenApiResponse(description='{"archived": <count>}'),
            **standard_error_responses(400, 401),
        },
    )
    @action(detail=False, methods=["post"], url_path="archive")
    def archive(self, request: Request) -> Response:
        serializer = BulkChatIdsRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = chat_service.archive_chats(
            user=request.user, chat_ids=serializer.validated_data["ids"]
        )
        return Response({"archived": count})

    @extend_schema(
        tags=["Chats"],
        summary="Unarchive chats",
        description="Restaura uno o varios chats archivados para el usuario autenticado.",
        request=BulkChatIdsRequest,
        responses={
            200: OpenApiResponse(description='{"unarchived": <count>}'),
            **standard_error_responses(400, 401),
        },
    )
    @action(detail=False, methods=["post"], url_path="unarchive")
    def unarchive(self, request: Request) -> Response:
        serializer = BulkChatIdsRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = chat_service.unarchive_chats(
            user=request.user, chat_ids=serializer.validated_data["ids"]
        )
        return Response({"unarchived": count})

    @extend_schema(
        methods=["POST"],
        tags=["Chats"],
        summary="Lock chat",
        description="Prevents all members from sending new messages. Owner only.",
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    @extend_schema(
        methods=["DELETE"],
        tags=["Chats"],
        summary="Unlock chat",
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    @action(detail=True, methods=["post", "delete"], url_path="lock")
    def lock(self, request: Request, pk=None) -> Response:
        if request.method == "POST":
            chat_service.lock_chat(user=request.user, chat_id=int(pk))
        else:
            chat_service.unlock_chat(user=request.user, chat_id=int(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        methods=["POST"],
        tags=["Chats"],
        summary="Mute chat",
        description="Silences this chat for the current user until the given datetime.",
        request=MuteChatRequest,
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(400, 401, 403, 404)},
    )
    @extend_schema(
        methods=["DELETE"],
        tags=["Chats"],
        summary="Unmute chat",
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    @action(detail=True, methods=["post", "delete"], url_path="mute")
    def mute(self, request: Request, pk=None) -> Response:
        if request.method == "POST":
            serializer = MuteChatRequest(data=request.data)
            serializer.is_valid(raise_exception=True)
            chat_service.mute_chat(
                user=request.user,
                chat_id=int(pk),
                muted_until=serializer.validated_data["muted_until"],
            )
        else:
            chat_service.unmute_chat(user=request.user, chat_id=int(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
