from rest_framework import serializers

from apps.notification.models import NotificationPreference


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "user_id",
            "inapp_enabled",
            "email_enabled",
            "mute_until",
            "updated_at",
        ]
        read_only_fields = ["user_id", "updated_at"]
        extra_kwargs = {
            "user_id": {"help_text": "ID del usuario. Solo lectura."},
            "inapp_enabled": {"help_text": "Habilita o deshabilita globalmente las notificaciones in-app."},
            "email_enabled": {"help_text": "Habilita o deshabilita globalmente el canal email."},
            "mute_until": {"help_text": "Silencia todas las notificaciones hasta este datetime (UTC)."},
            "updated_at": {"help_text": "Timestamp de la última modificación. Solo lectura."},
        }


class NotificationPreferenceUpdateSerializer(serializers.Serializer):
    inapp_enabled = serializers.BooleanField(required=False)
    email_enabled = serializers.BooleanField(required=False)
    mute_until = serializers.DateTimeField(required=False, allow_null=True)

    def validate_mute_until(self, value):
        if value is None:
            return value
        from django.utils import timezone
        if value <= timezone.now():
            raise serializers.ValidationError("mute_until must be a future datetime.")
        return value
