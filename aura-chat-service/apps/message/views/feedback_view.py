import logging

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.message.serializers.request import SetFeedbackRequest
from apps.message.serializers.response import FeedbackResponse
from apps.message.services.feedback_service import feedback_service
from core.authorization import AccessControl
from core.authorization.permissions import SET_MESSAGE_FEEDBACK
from core.openapi.common import standard_error_responses

logger = logging.getLogger(__name__)

_PATH_PARAMS = [
    OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
    OpenApiParameter(name="message_id", type=int, location=OpenApiParameter.PATH, required=True),
]


class FeedbackView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="Submit feedback for AI message",
        description=(
            "Creates or updates **thumbs up (1) / thumbs down (-1)** feedback for an **assistant (system)** message only. "
            "Validating the target message returns **400** if it is not an AI message."
        ),
        parameters=_PATH_PARAMS,
        request=SetFeedbackRequest,
        responses={200: FeedbackResponse, **standard_error_responses(400, 401, 403, 404)},
    )
    def post(self, request: Request, chat_id: int, message_id: int) -> Response:
        AccessControl.require_permissions(request.user, frozenset({SET_MESSAGE_FEEDBACK}))
        serializer = SetFeedbackRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        fb = feedback_service.set_feedback(
            user=request.user,
            chat_id=chat_id,
            message_id=message_id,
            value=serializer.validated_data["value"],
        )
        return Response(FeedbackResponse(fb).data)

    @extend_schema(
        tags=["Messages"],
        summary="Delete feedback",
        description="Removes the authenticated user's thumbs up/down on this message (if any).",
        parameters=_PATH_PARAMS,
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, chat_id: int, message_id: int) -> Response:
        AccessControl.require_permissions(request.user, frozenset({SET_MESSAGE_FEEDBACK}))
        feedback_service.delete_feedback(
            user=request.user, chat_id=chat_id, message_id=message_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
