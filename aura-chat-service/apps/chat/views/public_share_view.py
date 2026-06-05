import uuid
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.services.share_link_service import share_link_service
from apps.artifact_message.serializers import MessageResponse
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination


class PublicShareMessagesView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Share Links"],
        summary="Read-only chat history via share link",
        description=(
                "**No Bearer auth.** Path `token` is the UUID returned when creating a share link. "
                "Returns message rows with page-number pagination. Invalid or revoked links yield **404**."
        ),
        auth=[],
        parameters=[
            OpenApiParameter(
                name="token",
                type=str,
                location=OpenApiParameter.PATH,
                required=True,
                description="UUID token from `ShareLinkResponse.token`.",
            ),
        ],
        responses={200: MessageResponse(many=True), **standard_error_responses(400, 404)},
    )
    def get(self, request: Request, token: uuid.UUID) -> Response:
        messages = share_link_service.get_public_messages(token)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(messages, request)
        return paginator.get_paginated_response(MessageResponse(page, many=True).data)
