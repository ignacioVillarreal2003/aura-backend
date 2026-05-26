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
            "updated_at",
        ]
        read_only_fields = ["user_id", "updated_at"]
        extra_kwargs = {
            "user_id": {"help_text": "ID del usuario. Solo lectura."},
            "inapp_enabled": {
                "help_text": (
                    "Habilita o deshabilita globalmente las notificaciones in-app. "
                    "Si es `false`, ningún evento in-app llega al usuario, "
                    "independientemente de los overrides por evento."
                )
            },
            "email_enabled": {
                "help_text": (
                    "Habilita o deshabilita globalmente el canal email. "
                    "Si es `false`, ningún email se envía al usuario, "
                    "independientemente de los overrides por evento."
                )
            },
            "mute_until": {
                "help_text": (
                    "Silencia todas las notificaciones hasta este datetime (UTC). "
                    "Mientras el momento actual sea anterior a `mute_until`, "
                    "ningún evento se entrega. Null si no hay mute activo."
                )
            },
            "updated_at": {"help_text": "Timestamp de la última modificación. Solo lectura."},
        }


class NotificationPreferenceUpdateSerializer(serializers.Serializer):
    inapp_enabled = serializers.BooleanField(
        required=False,
        help_text="Habilita (`true`) o deshabilita (`false`) globalmente las notificaciones in-app.",
    )
    email_enabled = serializers.BooleanField(
        required=False,
        help_text="Habilita (`true`) o deshabilita (`false`) globalmente el canal email.",
    )
    mute_until = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text=(
            "Silencia todas las notificaciones hasta este datetime (debe ser futuro). "
            "Enviar `null` para eliminar el mute activo."
        ),
    )

    def validate_mute_until(self, value):
        if value is None:
            return value
        from django.utils import timezone
        if value <= timezone.now():
            raise serializers.ValidationError("mute_until must be a future datetime.")
        return value


class EventChannelStatesSerializer(serializers.Serializer):
    inapp = serializers.BooleanField(required=False)
    email = serializers.BooleanField(required=False)


class EventPreferencesEntrySerializer(serializers.Serializer):
    event_type = serializers.CharField(
        help_text="Identificador del tipo de evento (p. ej. `chat.member.invited`)."
    )
    type = serializers.CharField(
        help_text="Categoría del evento: `system`, `admin`, `user`, `event`."
    )
    severity = serializers.CharField(
        help_text="Severidad: `info`, `success`, `warning`, `critical`."
    )
    description = serializers.CharField(
        help_text="Descripción legible del evento."
    )
    default_channels = serializers.ListField(
        child=serializers.CharField(),
        help_text="Canales activos por defecto si el usuario no tiene overrides.",
    )
    available_channels = serializers.ListField(
        child=serializers.CharField(),
        help_text="Canales que el usuario puede configurar para este evento.",
    )
    is_silenceable = serializers.BooleanField(
        help_text=(
            "Si es `false`, el evento ignora preferencias del usuario y siempre se entrega. "
            "Esto aplica a eventos críticos como `auth.password.changed`."
        )
    )
    channels = serializers.DictField(
        child=serializers.BooleanField(),
        help_text=(
            "Estado efectivo por canal para este usuario. "
            "Combina el default del evento con el override del usuario (si existe). "
            "Claves: `inapp`, `email`. Valor `true` = habilitado, `false` = deshabilitado."
        ),
    )


class EventPreferenceUpdateSerializer(serializers.Serializer):
    inapp_enabled = serializers.BooleanField(
        required=False,
        help_text="Habilita (`true`) o deshabilita (`false`) las notificaciones in-app para este evento.",
    )
    email_enabled = serializers.BooleanField(
        required=False,
        help_text="Habilita (`true`) o deshabilita (`false`) los emails para este evento.",
    )

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
