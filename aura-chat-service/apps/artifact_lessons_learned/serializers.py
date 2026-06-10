from rest_framework import serializers

from apps.artifact.models.artifact import Artifact
from apps.artifact.shared_serializers import FragmentSerializer as _FragmentSerializer, \
    MessageSerializer as _MessageSerializer
from apps.artifact_lessons_learned.models import ArtifactLessonsLearned, ArtifactLessonsLearnedItem
from core.validators.audio import MAX_AUDIO_MB as _MAX_AUDIO_MB, SUPPORTED_AUDIO_TYPES as _SUPPORTED_AUDIO_TYPES


class GenerateLessonsLearnedRequest(serializers.Serializer):
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


class LessonsLearnedItemResponse(serializers.ModelSerializer):
    class Meta:
        model = ArtifactLessonsLearnedItem
        fields = ["id", "category", "observation", "discussion", "recommendation", "position"]


class LessonsLearnedResponse(serializers.ModelSerializer):
    items = LessonsLearnedItemResponse(many=True)
    mode = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactLessonsLearned
        fields = [
            "id",
            "artifact_id",
            "title",
            "query",
            "context",
            "mode",
            "items",
            "source_chat_id",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_mode(self, obj) -> str:
        return obj.artifact.mode if obj.artifact_id else ""

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None


class LessonsLearnedGenerateResponse(serializers.Serializer):
    lessons_learned = serializers.SerializerMethodField()
    messages = _MessageSerializer(many=True)
    fragments = _FragmentSerializer(many=True)

    def get_lessons_learned(self, obj):
        return LessonsLearnedResponse(obj["lessons_learned"]).data


class LessonsLearnedListResponse(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()
    mode = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model = ArtifactLessonsLearned
        fields = [
            "id",
            "artifact_id",
            "title",
            "mode",
            "source_chat_id",
            "item_count",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_item_count(self, obj: ArtifactLessonsLearned) -> int:
        return getattr(obj, "item_count", 0)

    def get_mode(self, obj) -> str:
        return obj.artifact.mode if obj.artifact_id else ""

    def get_source_chat_id(self, obj) -> int | None:
        return obj.artifact.source_chat_id if obj.artifact_id else None
