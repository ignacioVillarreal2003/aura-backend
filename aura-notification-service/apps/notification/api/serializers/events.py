from rest_framework import serializers

from apps.notification.events import is_known_event


class EventTypeCatalogueEntrySerializer(serializers.Serializer):
    event_type = serializers.CharField(
        help_text="Identificador único del tipo de evento (p. ej. `chat.member.invited`)."
    )
    type = serializers.CharField(
        help_text="Categoría del evento: `system`, `admin`, `event`."
    )
    severity = serializers.CharField(
        help_text="Severidad del evento: `info`, `success`, `warning`, `critical`."
    )
    description = serializers.CharField(
        help_text="Descripción legible del evento para mostrar en la UI."
    )
    default_channels = serializers.ListField(
        child=serializers.CharField(),
        help_text="Canales activos por defecto: `inapp`, `email`.",
    )
    available_channels = serializers.ListField(
        child=serializers.CharField(),
        help_text="Canales soportados para este evento.",
    )
    is_silenceable = serializers.BooleanField(
        help_text="Si es `false`, el evento se entrega siempre independientemente de las preferencias globales."
    )


class EventEmissionRequestSerializer(serializers.Serializer):
    event_type = serializers.CharField(
        max_length=128,
        help_text="Tipo de evento a emitir. Debe existir en el registro del servicio.",
    )
    recipient_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=10000,
        help_text="Lista de IDs de usuarios destinatarios.",
    )
    actor_id = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
        help_text="ID del usuario que realizó la acción que originó el evento.",
    )
    actor_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Nombre visible del actor.",
    )
    context = serializers.DictField(
        required=False,
        help_text="Datos adicionales del evento. Se usan para plantillas y se guardan en `data`.",
    )
    link_url = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text="Deep link opcional. Si se omite, el servicio puede construirlo desde `context`.",
    )

    def validate_event_type(self, value: str) -> str:
        if not is_known_event(value):
            raise serializers.ValidationError(f"Unknown event_type '{value}'.")
        return value


class EventDispatchOutcomeSerializer(serializers.Serializer):
    receiver_id = serializers.IntegerField(help_text="ID del usuario destinatario.")
    notification_id = serializers.IntegerField(
        allow_null=True,
        help_text="ID de la notificación in-app creada, si aplica.",
    )
    channels = serializers.DictField(
        child=serializers.CharField(),
        help_text="Mapa canal → estado: `sent`, `pending`, `skipped`.",
    )


class EventEmissionResponseSerializer(serializers.Serializer):
    event_type = serializers.CharField(help_text="El mismo `event_type` enviado en el request.")
    created = serializers.IntegerField(help_text="Cantidad de notificaciones in-app nuevas creadas.")
    skipped = serializers.IntegerField(help_text="Cantidad de canales omitidos por preferencias del usuario.")
    pending_email = serializers.IntegerField(help_text="Cantidad de emails encolados con estado `pending`.")
    outcomes = EventDispatchOutcomeSerializer(
        many=True,
        help_text="Detalle del resultado por cada receptor en `recipient_ids`.",
    )
