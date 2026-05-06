from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.message.exceptions import MessageAccessDeniedException
from apps.membership.repositories.membership_repository import membership_repository
from core.openapi.common import standard_error_responses


class MarkAsReadView(APIView):
    http_method_names = ["post"]

    @extend_schema(
        tags=["Messages"],
        summary="Mark chat as read",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        request=None,
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403)},
    )
    def post(self, request: Request, chat_id: int) -> Response:
        if not membership_repository.is_active_member(chat_id, request.user.id):
            raise MessageAccessDeniedException()
        membership_repository.mark_as_read(chat_id, request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)
