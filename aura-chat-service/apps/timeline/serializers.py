from django.conf import settings
from rest_framework import serializers

from apps.timeline.models import Timeline, TimelineEvent

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


class GenerateTimelineRequest(serializers.Serializer):
    mode = serializers.ChoiceField(choices=Timeline.Mode.choices)
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


class TimelineEventResponse(serializers.ModelSerializer):
    class Meta:
        model = TimelineEvent
        fields = [
            "id",
            "event",
            "description",
            "occurred_at",
            "occurred_label",
            "source_document_id",
            "position",
        ]


class TimelineResponse(serializers.ModelSerializer):
    events = TimelineEventResponse(many=True)

    class Meta:
        model = Timeline
        fields = [
            "id",
            "title",
            "summary",
            "mode",
            "events",
            "source_chat_id",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]
        read_only_fields = fields


class TimelineGenerateResponse(serializers.Serializer):
    timeline = serializers.SerializerMethodField()
    messages = _MessageSerializer(many=True)
    fragments = _FragmentSerializer(many=True)

    def get_timeline(self, obj):
        return TimelineResponse(obj["timeline"]).data


class _UpdateEventRequest(serializers.Serializer):
    event = serializers.CharField(max_length=300)
    description = serializers.CharField(default="", allow_blank=True)
    occurred_at = serializers.DateTimeField(required=False, allow_null=True)
    occurred_label = serializers.CharField(max_length=100, default="", allow_blank=True)
    source_document_id = serializers.IntegerField(required=False, allow_null=True)
    position = serializers.IntegerField(min_value=0)


class UpdateTimelineRequest(serializers.Serializer):
    title = serializers.CharField(max_length=500, allow_blank=False, required=False)
    summary = serializers.CharField(allow_blank=True, required=False)
    events = _UpdateEventRequest(many=True, required=False)

    def validate(self, data):
        if not data:
            raise serializers.ValidationError("Se requiere al menos un campo a actualizar.")
        return data

    def validate_events(self, value):
        if len(value) > 300:
            raise serializers.ValidationError("La línea de tiempo no puede superar los 300 eventos.")
        return value


class TimelineListResponse(serializers.ModelSerializer):
    event_count = serializers.SerializerMethodField()

    class Meta:
        model = Timeline
        fields = [
            "id",
            "title",
            "mode",
            "source_chat_id",
            "event_count",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_event_count(self, obj: Timeline) -> int:
        return getattr(obj, "event_count", 0)
