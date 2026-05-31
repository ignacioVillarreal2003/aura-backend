from django.conf import settings
from rest_framework import serializers

from apps.checklist.models import Checklist, ChecklistItem, ChecklistSection

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


class GenerateChecklistRequest(serializers.Serializer):
    mode = serializers.ChoiceField(choices=Checklist.Mode.choices)
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


class ChecklistItemResponse(serializers.ModelSerializer):
    class Meta:
        model = ChecklistItem
        fields = ["id", "text", "is_checked", "notes", "position"]


class ChecklistSectionResponse(serializers.ModelSerializer):
    items = ChecklistItemResponse(many=True)

    class Meta:
        model = ChecklistSection
        fields = ["id", "title", "position", "items"]


class ChecklistResponse(serializers.ModelSerializer):
    sections = ChecklistSectionResponse(many=True)

    class Meta:
        model = Checklist
        fields = [
            "id",
            "title",
            "mode",
            "sections",
            "source_chat_id",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]
        read_only_fields = fields


class ChecklistGenerateResponse(serializers.Serializer):
    checklist = serializers.SerializerMethodField()
    messages = _MessageSerializer(many=True)
    fragments = _FragmentSerializer(many=True)

    def get_checklist(self, obj):
        return ChecklistResponse(obj["checklist"]).data


class _UpdateItemRequest(serializers.Serializer):
    text = serializers.CharField(max_length=500)
    is_checked = serializers.BooleanField(default=False)
    notes = serializers.CharField(default="", allow_blank=True)
    position = serializers.IntegerField(min_value=0)


class _UpdateSectionRequest(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    position = serializers.IntegerField(min_value=0)
    items = _UpdateItemRequest(many=True)


class UpdateChecklistRequest(serializers.Serializer):
    title = serializers.CharField(max_length=500, allow_blank=False, required=False)
    sections = _UpdateSectionRequest(many=True, required=False)

    def validate(self, data):
        if not data:
            raise serializers.ValidationError("Se requiere al menos un campo a actualizar.")
        return data

    def validate_sections(self, value):
        total = sum(len(sec.get("items", [])) for sec in value)
        if total > 200:
            raise serializers.ValidationError("La checklist no puede superar los 200 ítems.")
        return value


class ChecklistListResponse(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()
    checked_count = serializers.SerializerMethodField()

    class Meta:
        model = Checklist
        fields = [
            "id",
            "title",
            "mode",
            "source_chat_id",
            "item_count",
            "checked_count",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_item_count(self, obj: Checklist) -> int:
        return getattr(obj, "item_count", 0)

    def get_checked_count(self, obj: Checklist) -> int:
        return getattr(obj, "checked_count", 0)
