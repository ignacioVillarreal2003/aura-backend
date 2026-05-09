from rest_framework import serializers

from apps.notification.events import is_known_event
from apps.notification.models import PreferenceChannel


class EventTypeCatalogueEntrySerializer(serializers.Serializer):
    event_type = serializers.CharField()
    type = serializers.CharField()
    severity = serializers.CharField()
    description = serializers.CharField()
    default_channels = serializers.ListField(child=serializers.CharField())
    available_channels = serializers.ListField(child=serializers.CharField())
    is_silenceable = serializers.BooleanField()


class EventEmissionRequestSerializer(serializers.Serializer):
    event_type = serializers.CharField(max_length=128)
    recipient_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=10000,
    )
    actor_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    actor_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    context = serializers.DictField(required=False)
    idempotency_key = serializers.CharField(max_length=128, required=False, allow_blank=False)
    link_url = serializers.URLField(required=False, allow_blank=True)
    target_scope = serializers.CharField(max_length=64, required=False)
    target_label = serializers.CharField(max_length=255, required=False, allow_blank=True)
    channels_override = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[PreferenceChannel.INAPP, PreferenceChannel.EMAIL]
        ),
        required=False,
        allow_empty=False,
    )

    def validate_event_type(self, value: str) -> str:
        if not is_known_event(value):
            raise serializers.ValidationError(f"Unknown event_type '{value}'.")
        return value


class EventDispatchOutcomeSerializer(serializers.Serializer):
    receiver_id = serializers.IntegerField()
    notification_id = serializers.IntegerField(allow_null=True)
    channels = serializers.DictField(child=serializers.CharField())
    suppressed = serializers.BooleanField()


class EventEmissionResponseSerializer(serializers.Serializer):
    event_type = serializers.CharField()
    created = serializers.IntegerField()
    suppressed = serializers.IntegerField()
    skipped = serializers.IntegerField()
    pending_email = serializers.IntegerField()
    outcomes = EventDispatchOutcomeSerializer(many=True)


class LegacyAdminCreateRequestSerializer(serializers.Serializer):
    receiver_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
    )
    message = serializers.CharField(max_length=500)
    type = serializers.CharField(max_length=64, required=False)
    target_scope = serializers.CharField(max_length=64, required=False, default="individual")
    target_label = serializers.CharField(max_length=255, required=False, allow_blank=True)
    actor_user_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    actor_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    send_email = serializers.BooleanField(required=False, default=False)
    subject = serializers.CharField(max_length=255, required=False, allow_blank=True)


class LegacyAdminCreateResponseSerializer(serializers.Serializer):
    created = serializers.IntegerField()
    suppressed = serializers.IntegerField()
    skipped = serializers.IntegerField()
    pending_email = serializers.IntegerField()
    notification_ids = serializers.ListField(child=serializers.IntegerField())
