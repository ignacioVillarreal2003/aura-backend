from django.conf import settings
from rest_framework import serializers


class SendThreadReplyRequest(serializers.Serializer):
    message = serializers.CharField(
        max_length=5000,
        allow_blank=False,
        help_text="Thread reply body (max 5000 characters).",
    )


class SetFeedbackRequest(serializers.Serializer):
    value = serializers.ChoiceField(
        choices=[1, -1],
        help_text="1 = thumbs up, -1 = thumbs down. Only applies to assistant messages.",
    )


_SUPPORTED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/webm",
    "audio/ogg", "audio/flac", "audio/x-wav", "audio/x-m4a",
}
_MAX_AUDIO_MB = int(getattr(settings, "AUDIO_MAX_UPLOAD_MB", 25))


class SendMessageRequest(serializers.Serializer):
    message = serializers.CharField(
        max_length=10000,
        required=False,
        allow_blank=False,
        help_text="Plain-text message. Omit when sending `audio` instead.",
    )
    audio = serializers.FileField(
        required=False,
        help_text="Single audio file for transcription; exclusive with `message` (max 25 MB, common MIME types).",
    )

    def validate_audio(self, file):
        content_type = getattr(file, "content_type", "")
        if content_type not in _SUPPORTED_AUDIO_TYPES:
            raise serializers.ValidationError(
                f"Unsupported format '{content_type}'. Allowed: mp3, mp4, wav, webm, ogg, flac."
            )
        if file.size > _MAX_AUDIO_MB * 1024 * 1024:
            raise serializers.ValidationError(f"Audio file cannot exceed {_MAX_AUDIO_MB} MB.")
        return file

    def validate(self, attrs):
        has_text = bool(attrs.get("message"))
        has_audio = bool(attrs.get("audio"))
        if not has_text and not has_audio:
            raise serializers.ValidationError("Provide either 'message' (text) or 'audio' (file).")
        if has_text and has_audio:
            raise serializers.ValidationError("Provide only one: 'message' or 'audio'.")
        return attrs
