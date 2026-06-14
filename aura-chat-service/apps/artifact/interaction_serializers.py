from rest_framework import serializers

from apps.artifact.models.artifact_feedback import ArtifactFeedback
from apps.artifact.models.artifact_pin import ArtifactPin
from apps.artifact.models.artifact_thread_reply import ArtifactThreadReply


class SetFeedbackRequest(serializers.Serializer):
    value = serializers.ChoiceField(
        choices=[1, -1],
        help_text="1 = pulgar arriba, -1 = pulgar abajo. Solo aplica a artefactos de respuesta de IA.",
    )
    reason = serializers.ChoiceField(
        choices=[c.value for c in ArtifactFeedback.Reason],
        required=False,
        allow_null=True,
        help_text=(
            "Motivo categorizado opcional. Pensado para el pulgar abajo (-1); se ignora en pulgar arriba."
        ),
    )
    comment = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=500,
        trim_whitespace=True,
        help_text="Detalle libre opcional (máx 500). Pensado para el pulgar abajo (-1).",
    )

    def validate(self, attrs):
        if attrs.get("value") == 1:
            attrs["reason"] = None
            attrs["comment"] = None
        else:
            attrs["comment"] = attrs.get("comment") or None
        return attrs


class SendThreadReplyRequest(serializers.Serializer):
    message = serializers.CharField(
        max_length=5000,
        allow_blank=False,
        help_text="Cuerpo de la respuesta de hilo (máx 5000 caracteres).",
    )


class UpdateThreadReplyRequest(serializers.Serializer):
    message = serializers.CharField(
        max_length=5000,
        allow_blank=False,
        help_text="Nuevo texto de la respuesta (máx 5000 caracteres).",
    )


class FeedbackResponse(serializers.ModelSerializer):
    class Meta:
        model = ArtifactFeedback
        fields = ["id", "artifact_id", "value", "reason", "comment", "created_by", "created_at", "updated_at"]
        read_only_fields = fields


class ThreadReplyResponse(serializers.ModelSerializer):
    class Meta:
        model = ArtifactThreadReply
        fields = [
            "id", "parent_artifact_id", "message",
            "created_by", "created_at",
            "updated_by", "updated_at",
        ]
        read_only_fields = fields


class ArtifactPinResponse(serializers.ModelSerializer):
    class Meta:
        model = ArtifactPin
        fields = ["id", "artifact_id", "created_by", "created_at"]
        read_only_fields = fields


class FeedbackSummarySerializer(serializers.Serializer):
    total = serializers.IntegerField(help_text="Total feedback entries in the window.")
    thumbs_up = serializers.IntegerField()
    thumbs_down = serializers.IntegerField()
    satisfaction_rate = serializers.FloatField(
        allow_null=True,
        help_text="thumbs_up / (thumbs_up + thumbs_down), or null when there is no feedback.",
    )


class FeedbackAssistantRowSerializer(serializers.Serializer):
    assistant_id = serializers.IntegerField(allow_null=True)
    assistant_name = serializers.CharField()
    total = serializers.IntegerField()
    thumbs_up = serializers.IntegerField()
    thumbs_down = serializers.IntegerField()
    satisfaction_rate = serializers.FloatField(allow_null=True)


class FeedbackReasonRowSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_null=True, help_text="Reason code, or null if unspecified.")
    count = serializers.IntegerField()


class FeedbackNegativeRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    artifact_id = serializers.IntegerField()
    assistant_id = serializers.IntegerField(allow_null=True)
    assistant_name = serializers.CharField()
    reason = serializers.CharField(allow_null=True)
    comment = serializers.CharField(allow_null=True)
    user_id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    message_excerpt = serializers.CharField(allow_blank=True)


class FeedbackAnalyticsResponse(serializers.Serializer):
    window_days = serializers.IntegerField()
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    summary = FeedbackSummarySerializer()
    assistants = FeedbackAssistantRowSerializer(many=True)
    reasons = FeedbackReasonRowSerializer(many=True)
    recent_negative = FeedbackNegativeRowSerializer(many=True)
