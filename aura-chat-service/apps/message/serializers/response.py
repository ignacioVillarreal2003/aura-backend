from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.artifact.models.artifact_message import ArtifactMessage
from apps.message.models.message_feedback import ArtifactFeedback
from apps.message.models.message_thread_reply import ArtifactThreadReply
from apps.message.models.pinned_message import ArtifactPin


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


class ThreadReplyResponse(serializers.ModelSerializer):
    class Meta:
        model = ArtifactThreadReply
        fields = ["id", "parent_artifact_id", "message", "created_by", "created_at"]


class FeedbackResponse(serializers.ModelSerializer):
    class Meta:
        model = ArtifactFeedback
        fields = ["id", "artifact_id", "user_id", "value", "reason", "comment", "created_at", "updated_at"]


class PinnedMessageResponse(serializers.ModelSerializer):
    artifact = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactPin
        fields = ["id", "chat_id", "artifact_id", "pinned_by", "pinned_at", "artifact"]

    @extend_schema_field(MessageResponse())
    def get_artifact(self, obj):
        artifact = getattr(obj, "artifact", None)
        if artifact is None:
            return None
        try:
            return MessageResponse(artifact.message_content).data
        except Exception:
            return None


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


class RegenerateResponseSerializer(serializers.Serializer):
    assistant = AssistantBlockSerializer(
        allow_null=True,
        required=False,
        help_text="New assistant turn after regeneration; null if generation failed.",
    )
    assistant_error = AssistantErrorSerializer(
        allow_null=True,
        required=False,
        help_text="Set when the LLM call failed.",
    )
