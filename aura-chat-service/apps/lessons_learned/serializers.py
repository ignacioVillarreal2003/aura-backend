from django.conf import settings
from rest_framework import serializers

from apps.lessons_learned.models import LessonsLearned, LessonsLearnedItem

_SUPPORTED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/webm",
    "audio/ogg", "audio/flac", "audio/x-wav", "audio/x-m4a",
}
_MAX_AUDIO_MB = int(getattr(settings, "AUDIO_MAX_UPLOAD_MB", 25))


class _MessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["human", "assistant"])
    content = serializers.CharField()


class _FragmentSerializer(serializers.Serializer):
    document = serializers.DictField(required=False)
    content = serializers.CharField(required=False, default="")


class GenerateLessonsLearnedRequest(serializers.Serializer):
    mode = serializers.ChoiceField(choices=LessonsLearned.Mode.choices)
    message = serializers.CharField(allow_blank=False, max_length=4000, required=False)
    audio = serializers.FileField(required=False)
    chat_id = serializers.IntegerField(required=False, allow_null=True)

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
        model = LessonsLearnedItem
        fields = ["id", "category", "observation", "discussion", "recommendation", "position"]


class LessonsLearnedResponse(serializers.ModelSerializer):
    items = LessonsLearnedItemResponse(many=True)

    class Meta:
        model = LessonsLearned
        fields = [
            "id",
            "title",
            "context",
            "what_went_well",
            "what_failed",
            "recommendations",
            "mode",
            "items",
            "source_chat_id",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]
        read_only_fields = fields


class LessonsLearnedGenerateResponse(serializers.Serializer):
    lessons_learned = serializers.SerializerMethodField()
    messages = _MessageSerializer(many=True)
    fragments = _FragmentSerializer(many=True)

    def get_lessons_learned(self, obj):
        return LessonsLearnedResponse(obj["lessons_learned"]).data


class _UpdateItemRequest(serializers.Serializer):
    category = serializers.ChoiceField(choices=LessonsLearnedItem.Category.choices)
    observation = serializers.CharField()
    discussion = serializers.CharField(default="", allow_blank=True)
    recommendation = serializers.CharField(default="", allow_blank=True)
    position = serializers.IntegerField(min_value=0)


class UpdateLessonsLearnedRequest(serializers.Serializer):
    title = serializers.CharField(max_length=500, allow_blank=False, required=False)
    context = serializers.CharField(allow_blank=True, required=False)
    what_went_well = serializers.CharField(allow_blank=True, required=False)
    what_failed = serializers.CharField(allow_blank=True, required=False)
    recommendations = serializers.CharField(allow_blank=True, required=False)
    items = _UpdateItemRequest(many=True, required=False)

    def validate(self, data):
        if not data:
            raise serializers.ValidationError("Se requiere al menos un campo a actualizar.")
        return data

    def validate_items(self, value):
        if len(value) > 300:
            raise serializers.ValidationError("No se pueden superar las 300 lecciones.")
        return value


class LessonsLearnedListResponse(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = LessonsLearned
        fields = [
            "id",
            "title",
            "mode",
            "source_chat_id",
            "item_count",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_item_count(self, obj: LessonsLearned) -> int:
        return getattr(obj, "item_count", 0)
