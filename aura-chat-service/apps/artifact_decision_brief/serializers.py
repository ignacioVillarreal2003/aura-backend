from django.conf import settings
from rest_framework import serializers

from apps.artifact.models.artifact import Artifact
from apps.artifact.shared_serializers import FragmentSerializer as _FragmentSerializer, MessageSerializer as _MessageSerializer
from apps.artifact_decision_brief.models import ArtifactDecisionBrief, ArtifactDecisionBriefOption

_SUPPORTED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/webm",
    "audio/ogg", "audio/flac", "audio/x-wav", "audio/x-m4a",
}
_MAX_AUDIO_MB = int(getattr(settings, "AUDIO_MAX_UPLOAD_MB", 25))


class GenerateDecisionBriefRequest(serializers.Serializer):
    mode = serializers.ChoiceField(choices=Artifact.Mode.choices)
    message = serializers.CharField(allow_blank=False, max_length=4000, required=False)
    audio = serializers.FileField(required=False)
    chat_id = serializers.IntegerField()

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


class DecisionBriefOptionResponse(serializers.ModelSerializer):
    class Meta:
        model = ArtifactDecisionBriefOption
        fields = ["id", "title", "description", "pros", "cons", "is_recommended", "position"]


class DecisionBriefResponse(serializers.ModelSerializer):
    options = DecisionBriefOptionResponse(many=True)
    title = serializers.SerializerMethodField()
    mode = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactDecisionBrief
        fields = [
            "id",
            "artifact_id",
            "title",
            "problem",
            "context",
            "risks",
            "recommendation",
            "mode",
            "options",
            "source_chat_id",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]
        read_only_fields = fields

    def get_title(self, obj) -> str:
        return obj.artifact.title if obj.artifact_id else ""

    def get_mode(self, obj) -> str:
        return obj.artifact.mode if obj.artifact_id else ""

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None


class DecisionBriefGenerateResponse(serializers.Serializer):
    decision_brief = serializers.SerializerMethodField()
    messages = _MessageSerializer(many=True)
    fragments = _FragmentSerializer(many=True)

    def get_decision_brief(self, obj):
        return DecisionBriefResponse(obj["decision_brief"]).data


class _UpdateOptionRequest(serializers.Serializer):
    title = serializers.CharField(max_length=300)
    description = serializers.CharField(default="", allow_blank=True)
    pros = serializers.CharField(default="", allow_blank=True)
    cons = serializers.CharField(default="", allow_blank=True)
    is_recommended = serializers.BooleanField(default=False)
    position = serializers.IntegerField(min_value=0)


class UpdateDecisionBriefRequest(serializers.Serializer):
    title = serializers.CharField(max_length=500, allow_blank=False, required=False)
    problem = serializers.CharField(allow_blank=True, required=False)
    context = serializers.CharField(allow_blank=True, required=False)
    risks = serializers.CharField(allow_blank=True, required=False)
    recommendation = serializers.CharField(allow_blank=True, required=False)
    options = _UpdateOptionRequest(many=True, required=False)

    def validate(self, data):
        if not data:
            raise serializers.ValidationError("Se requiere al menos un campo a actualizar.")
        return data

    def validate_options(self, value):
        if len(value) > 50:
            raise serializers.ValidationError("El brief no puede superar las 50 opciones.")
        return value


class DecisionBriefListResponse(serializers.ModelSerializer):
    option_count = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    mode = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactDecisionBrief
        fields = [
            "id",
            "artifact_id",
            "title",
            "mode",
            "source_chat_id",
            "option_count",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_option_count(self, obj: ArtifactDecisionBrief) -> int:
        return getattr(obj, "option_count", 0)

    def get_title(self, obj) -> str:
        return obj.artifact.title if obj.artifact_id else ""

    def get_mode(self, obj) -> str:
        return obj.artifact.mode if obj.artifact_id else ""

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None
