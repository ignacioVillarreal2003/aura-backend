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
    reason = serializers.ChoiceField(
        choices=[
            "incorrect", "incomplete", "off_topic", "tone", "too_long", "hallucination", "other",
        ],
        required=False,
        allow_null=True,
        help_text=(
            "Optional categorised reason. Intended for thumbs down (-1); ignored for thumbs up. "
            "One of: incorrect, incomplete, off_topic, tone, too_long, hallucination, other."
        ),
    )
    comment = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=500,
        trim_whitespace=True,
        help_text="Optional free-text detail (max 500 chars). Intended for thumbs down (-1).",
    )

    def validate(self, attrs):
        # Reason/comment only carry meaning for negative feedback; drop them on thumbs up
        # so a later "up" never inherits a stale dislike reason from the same upsert row.
        if attrs.get("value") == 1:
            attrs["reason"] = None
            attrs["comment"] = None
        else:
            comment = attrs.get("comment")
            attrs["comment"] = comment or None
        return attrs


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
    mode = serializers.ChoiceField(
        choices=["document_question", "general_chat", "rag_agent", "agent"],
        required=False,
        default="document_question",
        help_text=(
            "AI reply flow to run after the message is stored. "
            "`document_question` (default) = RAG over the user's documents, "
            "`general_chat` = general-purpose assistant (no RAG), "
            "`rag_agent` = full RAG agent pipeline, "
            "`agent` = tool-using agent."
        ),
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
