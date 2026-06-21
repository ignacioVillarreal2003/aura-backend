from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.artifact_message.models import ArtifactMessage
from core.validators.audio import MAX_AUDIO_MB as _MAX_AUDIO_MB, SUPPORTED_AUDIO_TYPES as _SUPPORTED_AUDIO_TYPES


class SendMessageRequest(serializers.Serializer):
    chat_id = serializers.IntegerField(help_text="ID del chat al que pertenece el mensaje.")
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
    retrieve_context = serializers.BooleanField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Recuperar contexto de la base de conocimiento. Si se omite, usa el default del servicio.",
    )
    process_documents = serializers.BooleanField(
        required=False,
        allow_null=True,
        default=None,
        help_text="Procesar el contenido completo de los documentos adjuntos. Si se omite, usa el default del servicio.",
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


class MessageResponse(serializers.ModelSerializer):
    chat_id = serializers.SerializerMethodField()
    fragments = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()
    user_feedback = serializers.SerializerMethodField()
    user_feedback_reason = serializers.SerializerMethodField()
    user_feedback_comment = serializers.SerializerMethodField()
    thread_reply_count = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactMessage
        fields = [
            "id",
            "artifact_id",
            "chat_id",
            "message",
            "sender_type",
            "created_by",
            "created_at",
            "is_bookmarked",
            "user_feedback",
            "user_feedback_reason",
            "user_feedback_comment",
            "thread_reply_count",
            "fragments",
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_chat_id(self, obj) -> int | None:
        artifact = getattr(obj, "artifact", None)
        if artifact is not None:
            return artifact.source_chat_id
        return None

    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_fragments(self, obj):
        artifact = getattr(obj, "artifact", None)
        if artifact is not None:
            return artifact.fragments
        return None

    @extend_schema_field(
        serializers.BooleanField(
            help_text="True if the current user bookmarked this artifact (when annotated).",
        )
    )
    def get_is_bookmarked(self, obj) -> bool:
        return getattr(obj, "is_bookmarked", False) or False

    @extend_schema_field(
        serializers.IntegerField(
            allow_null=True,
            help_text="Current user's feedback value: 1, -1, or null if not set (when annotated).",
        )
    )
    def get_user_feedback(self, obj) -> int | None:
        return getattr(obj, "user_feedback", None)

    @extend_schema_field(
        serializers.CharField(
            allow_null=True,
            help_text="Current user's thumbs-down reason code, or null (when annotated).",
        )
    )
    def get_user_feedback_reason(self, obj) -> str | None:
        return getattr(obj, "user_feedback_reason", None)

    @extend_schema_field(
        serializers.CharField(
            allow_null=True,
            help_text="Current user's free-text feedback comment, or null (when annotated).",
        )
    )
    def get_user_feedback_comment(self, obj) -> str | None:
        return getattr(obj, "user_feedback_comment", None)

    @extend_schema_field(
        serializers.IntegerField(
            help_text="Count of thread replies for this artifact (when annotated).",
        )
    )
    def get_thread_reply_count(self, obj) -> int:
        return getattr(obj, "thread_reply_count", 0) or 0


class AssistantBlockSerializer(serializers.Serializer):
    question = serializers.CharField(
        allow_blank=True, help_text="Question or prompt fragment associated with the assistant turn."
    )
    answer = serializers.CharField(allow_blank=True, help_text="Main assistant answer text.")
    fragments = serializers.ListField(
        child=serializers.DictField(),
        default=list,
        help_text="Optional structured fragments from the LLM pipeline.",
    )


class AssistantErrorSerializer(serializers.Serializer):
    detail = serializers.CharField(help_text="Human-readable AI or infrastructure error.")


class SendMessagePostResponseSerializer(serializers.Serializer):
    message = MessageResponse(help_text="Persisted user message row as returned by the API.")
    transcript = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="Speech-to-text result when the request used `audio`; otherwise often null.",
    )
    assistant = AssistantBlockSerializer(
        allow_null=True,
        required=False,
        help_text="Assistant turn from the document-question flow when successful.",
    )
    assistant_error = AssistantErrorSerializer(
        allow_null=True,
        required=False,
        help_text="Present when the LLM or pipeline failed after accepting the user message.",
    )
