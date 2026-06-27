from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.chat.repositories.chat_repository import ALLOWED_ORDERINGS
from apps.chat.serializers.request import BulkChatIdsRequest, CreateChatRequest, UpdateChatRequest
from apps.chat.serializers.response import ChatListResponse, ChatManageListResponse, ChatResponse
from apps.chat.services.chat_service import chat_service
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

_ORDERING_ENUM = sorted(ALLOWED_ORDERINGS)

_CHAT_ID_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="Chat ID",
)
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


def _parse_tags(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    tags = [t.strip() for t in raw.split(",") if t.strip()]
    return tags or None


def _list_filters(request: Request) -> dict:
    ordering = request.query_params.get("ordering") or None
    if ordering not in ALLOWED_ORDERINGS:
        ordering = None
    return {
        "search": request.query_params.get("search") or None,
        "ordering": ordering,
        "tags": _parse_tags(request.query_params.get("tags")),
    }


@extend_schema_view(
    list=extend_schema(
        tags=["Chats"],
        summary="List chats",
        description=(
                "Paginated list of chats the user can access. Filter by `search`, `ordering`, and comma-separated `tags` "
                "(ALL tags must match). Rows use **ChatListResponse** (unread counts, pin state, archive)."
        ),
        parameters=[_SEARCH_PARAM, _ORDERING_PARAM, _TAGS_PARAM],
        responses={200: ChatListResponse(many=True), **standard_error_responses(401)},
    ),
    create=extend_schema(
        tags=["Chats"],
        summary="Create chat",
        description=(
                "Creates a new chat with optional system prompt, response style, and tags."
        ),
        request=CreateChatRequest,
        responses={201: ChatResponse, **standard_error_responses(400, 401)},
    ),
    retrieve=extend_schema(
        tags=["Chats"],
        summary="Get chat",
        description="Returns full **ChatResponse** for one chat id (membership and permissions enforced server-side).",
        parameters=[_CHAT_ID_PARAM],
        responses={200: ChatResponse, **standard_error_responses(401, 403, 404)},
    ),
    partial_update=extend_schema(
        tags=["Chats"],
        summary="Update chat",
        description="Partial update of name, prompts, style, and tags.",
        parameters=[_CHAT_ID_PARAM],
        request=UpdateChatRequest,
        responses={200: ChatResponse, **standard_error_responses(400, 401, 403, 404)},
    ),
    destroy=extend_schema(
        tags=["Chats"],
        summary="Delete chat",
        description="Deletes the chat for allowed roles (service rules apply).",
        parameters=[_CHAT_ID_PARAM],
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    ),
    my_chats=extend_schema(
        tags=["Chats"],
        summary="List chats created by me",
        description="Same filters as list but only chats **created by** the authenticated user.",
        parameters=[_SEARCH_PARAM, _ORDERING_PARAM, _TAGS_PARAM],
        responses={200: ChatListResponse(many=True), **standard_error_responses(401)},
    ),
    manage=extend_schema(
        tags=["Chats"],
        summary="List all chats (admin)",
        description="Paginated list of **all** chats from every user. Requires `MANAGE_CHATS` permission.",
        parameters=[_SEARCH_PARAM, _ORDERING_PARAM, _TAGS_PARAM],
        responses={200: ChatManageListResponse(many=True), **standard_error_responses(401, 403)},
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
        chats = chat_service.list_chats(user=request.user, **_list_filters(request))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(chats, request)
        return paginator.get_paginated_response(ChatListResponse(page, many=True).data)

    def retrieve(self, request: Request, chat_id=None) -> Response:
        chat = chat_service.get_chat(user=request.user, chat_id=chat_id)
        return Response(ChatResponse(chat).data)

    def partial_update(self, request: Request, chat_id=None) -> Response:
        serializer = UpdateChatRequest(data=request.data)
        serializer.is_valid(raise_exception=True)

        chat = chat_service.update_chat(
            user=request.user,
            chat_id=chat_id,
            **serializer.validated_data,
        )
        return Response(ChatResponse(chat).data)

    def destroy(self, request: Request, chat_id=None) -> Response:
        chat_service.delete_chat(user=request.user, chat_id=chat_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="manage")
    def manage(self, request: Request) -> Response:
        chats = chat_service.list_all_chats(user=request.user, **_list_filters(request))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(chats, request)
        return paginator.get_paginated_response(ChatManageListResponse(page, many=True).data)

    @action(detail=False, methods=["get"], url_path="me")
    def my_chats(self, request: Request) -> Response:
        chats = chat_service.list_own_chats(user=request.user, **_list_filters(request))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(chats, request)
        return paginator.get_paginated_response(ChatListResponse(page, many=True).data)

    @extend_schema(
        methods=["POST"],
        tags=["Chats"],
        summary="Pin chat",
        description="Pins this chat for the current user so it sorts to the top of list views.",
        parameters=[_CHAT_ID_PARAM],
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    @extend_schema(
        methods=["DELETE"],
        tags=["Chats"],
        summary="Unpin chat",
        description="Removes the user-level pin for this chat.",
        parameters=[_CHAT_ID_PARAM],
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    @action(detail=True, methods=["post", "delete"], url_path="pin")
    def pin(self, request: Request, chat_id=None) -> Response:
        if request.method == "POST":
            chat_service.pin_chat(user=request.user, chat_id=chat_id)
        else:
            chat_service.unpin_chat(user=request.user, chat_id=chat_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Chats"],
        summary="List archived chats",
        description=(
                "Lists chats **archived by** the user (not in the main inbox). Same query params as list (`search`, "
                "`ordering`, `tags`)."
        ),
        parameters=[_SEARCH_PARAM, _ORDERING_PARAM, _TAGS_PARAM],
        responses={200: ChatListResponse(many=True), **standard_error_responses(401)},
    )
    @action(detail=False, methods=["get"], url_path="archived")
    def archived(self, request: Request) -> Response:
        chats = chat_service.list_archived_chats(user=request.user, **_list_filters(request))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(chats, request)
        return paginator.get_paginated_response(ChatListResponse(page, many=True).data)

    @extend_schema(
        tags=["Chats"],
        summary="Archive chats",
        description=(
                "Archives one or more chats for the authenticated user. Archived threads disappear from the default list "
                "until unarchived."
        ),
        request=BulkChatIdsRequest,
        responses={
            200: OpenApiResponse(
                description="JSON object: `archived` = number of chats archived.",
            ),
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
        description="Restores one or more archived chats to the main inbox for the authenticated user.",
        request=BulkChatIdsRequest,
        responses={
            200: OpenApiResponse(
                description="JSON object: `unarchived` = number of chats restored.",
            ),
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
        tags=["Chats"],
        summary="Delete chats",
        description=(
                "Deletes one or more chats. Borrar es una acción global, por eso solo se "
                "eliminan los chats de los que el usuario es dueño/creador; el resto se omite."
        ),
        request=BulkChatIdsRequest,
        responses={
            200: OpenApiResponse(
                description="JSON object: `deleted` = number of chats deleted.",
            ),
            **standard_error_responses(400, 401),
        },
    )
    @action(detail=False, methods=["post"], url_path="delete")
    def delete_bulk(self, request: Request) -> Response:
        serializer = BulkChatIdsRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = chat_service.delete_chats(
            user=request.user, chat_ids=serializer.validated_data["ids"]
        )
        return Response({"deleted": count})

    @extend_schema(
        methods=["POST"],
        tags=["Chats"],
        summary="Lock chat",
        description="Prevents all members from sending new messages. Owner only.",
        parameters=[_CHAT_ID_PARAM],
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    @extend_schema(
        methods=["DELETE"],
        tags=["Chats"],
        summary="Unlock chat",
        description="Re-opens the chat so members can send messages again.",
        parameters=[_CHAT_ID_PARAM],
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    @action(detail=True, methods=["post", "delete"], url_path="lock")
    def lock(self, request: Request, chat_id=None) -> Response:
        if request.method == "POST":
            chat_service.lock_chat(user=request.user, chat_id=chat_id)
        else:
            chat_service.unlock_chat(user=request.user, chat_id=chat_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
