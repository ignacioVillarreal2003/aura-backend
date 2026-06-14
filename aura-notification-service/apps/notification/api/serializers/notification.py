from rest_framework import serializers

from apps.notification.models import Notification, NotificationStatus


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "receiver_id",
            "event_type",
            "message",
            "data",
            "severity",
            "link_url",
            "actor_name",
            "status",
            "read_at",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Identificador único de la notificación."},
            "receiver_id": {"help_text": "ID del usuario destinatario."},
            "event_type": {"help_text": "Tipo de evento registrado (p. ej. `chat.member.invited`)."},
            "message": {"help_text": "Texto renderizado de la notificación (máximo 500 caracteres)."},
            "data": {"help_text": "Contexto original del evento en formato JSON."},
            "severity": {"help_text": "Nivel de severidad: `info`, `success`, `warning`, `critical`."},
            "link_url": {"help_text": "Deep link opcional hacia la pantalla relevante en el frontend."},
            "actor_name": {"help_text": "Nombre del actor que generó la notificación."},
            "status": {"help_text": "Estado: `unread` o `read`."},
            "read_at": {"help_text": "Timestamp del momento en que se marcó como leída."},
            "created_by": {"help_text": "ID del actor que disparó la notificación."},
            "created_at": {"help_text": "Timestamp de creación."},
        }


class NotificationStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=NotificationStatus.choices,
        help_text="Nuevo estado: `unread` o `read`.",
    )


class MarkAllReadRequestSerializer(serializers.Serializer):
    until_id = serializers.IntegerField(
        min_value=1,
        required=False,
        help_text="Si se proporciona, solo se marcan como leídas las notificaciones con `id <= until_id`.",
    )


class BulkMarkReadResponseSerializer(serializers.Serializer):
    updated = serializers.IntegerField(
        help_text="Cantidad de notificaciones marcadas como leídas en esta operación."
    )


class UnreadCountSerializer(serializers.Serializer):
    count = serializers.IntegerField(
        help_text="Cantidad de notificaciones con estado `unread` del usuario autenticado."
    )
