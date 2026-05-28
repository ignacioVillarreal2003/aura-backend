from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.message.services.message_service import message_service
from core.openapi.common import standard_error_responses


class MessageDeleteView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Delete a message",
        description="Soft-deletes a message. **Only the chat owner** can delete messages.",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(name="message_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, chat_id: int, message_id: int) -> Response:
        message_service.delete_message(
            user=request.user,
            chat_id=chat_id,
            message_id=message_id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
