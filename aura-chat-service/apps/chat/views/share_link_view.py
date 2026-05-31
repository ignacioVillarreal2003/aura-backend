from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.serializers.share_link import ShareLinkCreateRequest, ShareLinkResponse
from apps.chat.services.share_link_service import share_link_service
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination


class ShareLinkListView(APIView):
    @extend_schema(
        tags=["Share Links"],
        summary="List share links for a chat",
        description="Paginated list of share-link records. By default only active links are returned. Pass `?active=false` to include revoked links.",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(name="active", type=bool, location=OpenApiParameter.QUERY, required=False, default=True),
        ],
        responses={200: ShareLinkResponse(many=True), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int) -> Response:
        active_only = request.query_params.get("active", "true").lower() != "false"
        links = share_link_service.list_links(user=request.user, chat_id=chat_id, active_only=active_only)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(links, request)
        return paginator.get_paginated_response(ShareLinkResponse(page, many=True).data)

    @extend_schema(
        tags=["Share Links"],
        summary="Create a share link",
        description=(
                "Creates a UUID **token** clients can pass to the public read-only endpoint "
                "`GET /api/v1/share/{token}/messages/` (no Bearer). Optional future `expires_at`."
        ),
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        request=ShareLinkCreateRequest,
        responses={201: ShareLinkResponse, **standard_error_responses(400, 401, 403, 404)},
    )
    def post(self, request: Request, chat_id: int) -> Response:
        serializer = ShareLinkCreateRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = share_link_service.create_link(
            user=request.user,
            chat_id=chat_id,
            expires_at=serializer.validated_data.get("expires_at"),
        )
        return Response(ShareLinkResponse(link).data, status=status.HTTP_201_CREATED)


class ShareLinkDetailView(APIView):
    @extend_schema(
        tags=["Share Links"],
        summary="Revoke a share link",
        description="Soft-deactivates the link so the public token no longer resolves to messages.",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(name="link_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, chat_id: int, link_id: int) -> Response:
        share_link_service.revoke_link(user=request.user, chat_id=chat_id, link_id=link_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
