from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artifact.audio import transcribe as _transcribe
from apps.artifact.exceptions import TranscriptionBusyException, TranscriptionException
from apps.artifact_message.services.message_service import message_service
from apps.chat.ws_rate_limit import check_transcribe_rate_limit
from core.openapi.common import standard_error_responses

_SUPPORTED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/webm",
    "audio/ogg", "audio/flac", "audio/x-wav", "audio/x-m4a",
}
_MAX_AUDIO_MB = int(getattr(settings, "AUDIO_MAX_UPLOAD_MB", 25))

_CHAT_ID_PATH_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
)


class TranscribeView(APIView):
    @extend_schema(
        tags=["Chats"],
        summary="Transcribe audio",
        description=(
                "Accepts a voice clip (`audio` multipart field) and returns its transcript. "
                "No message is saved and the AI is not invoked. "
                "Requires active chat membership, `SEND_MESSAGE`, and the chat must not be locked. "
                "Use this to convert audio to text before sending a message or generating an artifact."
        ),
        parameters=[_CHAT_ID_PATH_PARAM],
        responses={
            200: {"type": "object", "properties": {"transcript": {"type": "string"}}},
            **standard_error_responses(400, 401, 403, 502, 503),
        },
    )
    def post(self, request: Request, chat_id: int) -> Response:
        message_service.assert_send_access(request.user, chat_id)

        if not check_transcribe_rate_limit(request.user.id):
            return Response(
                {"detail": "Too many transcription requests. Please wait.", "error": "rate_limit_exceeded"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        audio = request.FILES.get("audio")
        if not audio:
            return Response({"detail": "No audio file provided."}, status=status.HTTP_400_BAD_REQUEST)
        content_type = getattr(audio, "content_type", "")
        if content_type not in _SUPPORTED_AUDIO_TYPES:
            return Response(
                {"detail": f"Unsupported audio format: {content_type}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if audio.size > _MAX_AUDIO_MB * 1024 * 1024:
            return Response(
                {"detail": f"Audio exceeds {_MAX_AUDIO_MB} MB limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            transcript = _transcribe(audio)
        except TranscriptionBusyException:
            raise
        except TranscriptionException:
            raise
        return Response({"transcript": transcript}, status=status.HTTP_200_OK)
