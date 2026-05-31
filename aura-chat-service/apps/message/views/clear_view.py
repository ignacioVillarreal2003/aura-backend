import logging
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.message.services.message_service import message_service
from core.openapi.common import standard_error_responses

logger = logging.getLogger(__name__)


class ClearHistoryView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Clear chat history",
        description="Soft-deletes all messages in the chat. Only the chat creator can do this.",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={
            204: OpenApiResponse(description="No content"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, chat_id: int) -> Response:
        message_service.clear_history(user=request.user, chat_id=chat_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
