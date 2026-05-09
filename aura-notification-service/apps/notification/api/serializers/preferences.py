from rest_framework import serializers

from apps.notification.models import (
    NotificationPreference,
    PreferenceChannel,
)


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "user_id",
            "inapp_enabled",
            "email_enabled",
            "mute_until",
            "quiet_hours_start",
            "quiet_hours_end",
            "quiet_hours_tz",
            "updated_at",
        ]
        read_only_fields = ["user_id", "updated_at"]


class NotificationPreferenceUpdateSerializer(serializers.Serializer):
    inapp_enabled = serializers.BooleanField(required=False)
    email_enabled = serializers.BooleanField(required=False)
    mute_until = serializers.DateTimeField(required=False, allow_null=True)
    quiet_hours_start = serializers.TimeField(required=False, allow_null=True)
    quiet_hours_end = serializers.TimeField(required=False, allow_null=True)
    quiet_hours_tz = serializers.CharField(max_length=64, required=False, allow_blank=False)

    def validate(self, attrs):
        if "quiet_hours_start" in attrs and "quiet_hours_end" not in attrs:
            raise serializers.ValidationError(
                "quiet_hours_end is required when quiet_hours_start is provided."
            )
        if "quiet_hours_end" in attrs and "quiet_hours_start" not in attrs:
            raise serializers.ValidationError(
                "quiet_hours_start is required when quiet_hours_end is provided."
            )
        return attrs


class EventChannelStatesSerializer(serializers.Serializer):
    inapp = serializers.BooleanField(required=False)
    email = serializers.BooleanField(required=False)


class EventPreferencesEntrySerializer(serializers.Serializer):
    event_type = serializers.CharField()
    type = serializers.CharField()
    severity = serializers.CharField()
    description = serializers.CharField()
    default_channels = serializers.ListField(child=serializers.CharField())
    available_channels = serializers.ListField(child=serializers.CharField())
    is_silenceable = serializers.BooleanField()
    channels = serializers.DictField(child=serializers.BooleanField())


class EventPreferenceUpdateSerializer(serializers.Serializer):
    inapp_enabled = serializers.BooleanField(required=False)
    email_enabled = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one of inapp_enabled or email_enabled is required."
            )
        return attrs

    def to_channel_pairs(self) -> list[tuple[str, bool]]:
        out: list[tuple[str, bool]] = []
        if "inapp_enabled" in self.validated_data:
            out.append((PreferenceChannel.INAPP, self.validated_data["inapp_enabled"]))
        if "email_enabled" in self.validated_data:
            out.append((PreferenceChannel.EMAIL, self.validated_data["email_enabled"]))
        return out
