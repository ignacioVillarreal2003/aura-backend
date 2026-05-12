from rest_framework import serializers

from apps.notification.events import is_known_event
from apps.notification.models import PreferenceChannel, TargetScope


class EventTypeCatalogueEntrySerializer(serializers.Serializer):
    event_type = serializers.CharField(
        help_text="Identificador único del tipo de evento (p. ej. `chat.member.invited`)."
    )
    type = serializers.CharField(
        help_text=(
            "Categoría del evento. "
            "Valores: `system` (sistema), `admin` (administrador), "
            "`user` (usuario), `event` (evento de dominio)."
        )
    )
    severity = serializers.CharField(
        help_text="Severidad del evento. Valores: `info`, `success`, `warning`, `critical`."
    )
    description = serializers.CharField(
        help_text="Descripción legible del evento para mostrar en la UI."
    )
    default_channels = serializers.ListField(
        child=serializers.CharField(),
        help_text=(
            "Canales activos por defecto si el usuario no tiene un override configurado. "
            "Valores posibles: `inapp`, `email`."
        ),
    )
    available_channels = serializers.ListField(
        child=serializers.CharField(),
        help_text="Canales que el usuario puede habilitar o deshabilitar para este evento.",
    )
    is_silenceable = serializers.BooleanField(
        help_text=(
            "Si es `false`, el evento se entrega siempre independientemente de las preferencias "
            "del usuario (mute, quiet hours, canal deshabilitado). "
            "Usado para notificaciones críticas de seguridad como cambio de contraseña."
        )
    )


class EventEmissionRequestSerializer(serializers.Serializer):
    event_type = serializers.CharField(
        max_length=128,
        help_text=(
            "Tipo de evento a emitir. Debe existir en el registro de eventos del servicio. "
            "Consultar `GET /api/v1/event-types/` para la lista completa."
        ),
    )
    recipient_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=10000,
        help_text=(
            "Lista de IDs de los usuarios destinatarios. "
            "Mínimo 1, máximo 10 000 por request. "
            "El servicio procesa las preferencias de cada usuario de forma independiente."
        ),
    )
    title = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=False,
        help_text=(
            "Título corto de la notificación. Se muestra en la bandeja y se usa como asunto del email. "
            "Si se omite, el frontend puede usar la `description` del tipo de evento como fallback."
        ),
    )
    actor_id = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
        help_text="ID del usuario que realizó la acción que originó el evento. Null si es del sistema.",
    )
    actor_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text=(
            "Nombre visible del actor. Se incluye en el campo `sender_name` de la notificación "
            "y puede usarse en las plantillas de email como `{{ actor_name }}`."
        ),
    )
    context = serializers.DictField(
        required=False,
        help_text=(
            "Datos adicionales del evento en formato JSON. Se usan para:\n"
            "- Renderizar las plantillas de texto e email.\n"
            "- Construir el `link_url` automáticamente (p. ej. `chat_id` para eventos de chat).\n"
            "- Se guarda como campo `data` en la notificación para uso del frontend.\n\n"
            "Optimización: si se incluye `recipient_email`, el worker de email lo usa directamente "
            "sin hacer un round-trip al servicio de autenticación."
        ),
    )
    idempotency_key = serializers.CharField(
        max_length=128,
        required=False,
        allow_blank=False,
        help_text=(
            "Clave única por receptor para deduplicar reintentos. "
            "Si ya existe una notificación activa con la misma combinación "
            "`(receiver_id, idempotency_key)`, el outcome de ese receptor tendrá `suppressed: true` "
            "y se devuelve la notificación existente sin crear una nueva."
        ),
    )
    link_url = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text=(
            "Deep link hacia la pantalla relevante en el frontend. "
            "Si el evento tiene un `link_builder` configurado y este campo se omite, "
            "el servicio construye el link automáticamente usando el `context`."
        ),
    )
    target_scope = serializers.ChoiceField(
        choices=TargetScope.choices,
        required=False,
        help_text=(
            "Alcance del destino. Por defecto `individual`. "
            "Valores: `individual`, `broadcast`, `role`."
        ),
    )
    target_label = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Etiqueta descriptiva del destino para mostrar en la UI (p. ej. nombre del equipo o proyecto).",
    )
    channels_override = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[PreferenceChannel.INAPP, PreferenceChannel.EMAIL]
        ),
        required=False,
        allow_empty=False,
        help_text=(
            "Fuerza canales específicos ignorando los `default_channels` del evento. "
            "Valores: `inapp`, `email`. Las preferencias del usuario siguen aplicando sobre estos canales. "
            "Si se omite, se usan los canales por defecto del evento."
        ),
    )

    def validate_event_type(self, value: str) -> str:
        if not is_known_event(value):
            raise serializers.ValidationError(f"Unknown event_type '{value}'.")
        return value


class EventDispatchOutcomeSerializer(serializers.Serializer):
    receiver_id = serializers.IntegerField(
        help_text="ID del usuario destinatario."
    )
    notification_id = serializers.IntegerField(
        allow_null=True,
        help_text=(
            "ID de la notificación in-app creada. "
            "Null si el canal inapp fue omitido o el evento no tiene canal inapp."
        ),
    )
    channels = serializers.DictField(
        child=serializers.CharField(),
        help_text=(
            "Mapa de canal → estado de despacho. "
            "Claves posibles: `inapp`, `email`. "
            "Valores: `sent` (entregado), `pending` (email encolado), "
            "`skipped` (omitido por preferencias), `suppressed` (duplicado por idempotency_key), "
            "`failed` (error al encolar)."
        ),
    )
    suppressed = serializers.BooleanField(
        help_text=(
            "True si ya existía una notificación activa con la misma `idempotency_key` "
            "para este receptor. La notificación existente no se modifica."
        )
    )


class EventEmissionResponseSerializer(serializers.Serializer):
    event_type = serializers.CharField(
        help_text="El mismo `event_type` enviado en el request."
    )
    created = serializers.IntegerField(
        help_text="Cantidad de notificaciones in-app nuevas creadas (no suprimidas)."
    )
    suppressed = serializers.IntegerField(
        help_text="Cantidad de receptores donde la notificación ya existía (deduplicada por `idempotency_key`)."
    )
    skipped = serializers.IntegerField(
        help_text=(
            "Cantidad de canales omitidos por preferencias del usuario "
            "(canal deshabilitado, mute activo, quiet hours)."
        )
    )
    pending_email = serializers.IntegerField(
        help_text="Cantidad de emails encolados en Celery con estado `pending`."
    )
    outcomes = EventDispatchOutcomeSerializer(
        many=True,
        help_text="Detalle del resultado por cada receptor en `recipient_ids`.",
    )
