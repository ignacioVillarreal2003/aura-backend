from rest_framework import serializers

from apps.notification.models import Notification, NotificationStatus


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "receiver_id",
            "title",
            "message",
            "type",
            "event_type",
            "event_key",
            "data",
            "severity",
            "link_url",
            "sender_name",
            "target_scope",
            "target_label",
            "status",
            "read_at",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "id": {"help_text": "Identificador único de la notificación."},
            "receiver_id": {"help_text": "ID del usuario destinatario."},
            "title": {"help_text": "Título corto de la notificación. Se usa como asunto en emails. Null si no fue especificado."},
            "message": {"help_text": "Texto renderizado de la notificación (máximo 500 caracteres)."},
            "type": {
                "help_text": (
                    "Categoría de la notificación. "
                    "Valores: `system` (sistema), `admin` (administrador), "
                    "`user` (usuario), `event` (evento de dominio)."
                )
            },
            "event_type": {
                "help_text": (
                    "Identificador del tipo de evento que originó la notificación "
                    "(p. ej. `chat.member.invited`, `auth.new_login`). "
                    "Null si no proviene de un evento registrado."
                )
            },
            "event_key": {
                "help_text": (
                    "Clave de idempotencia usada al crear la notificación. "
                    "Corresponde al `idempotency_key` enviado por el productor."
                )
            },
            "data": {
                "help_text": (
                    "Contexto original del evento en formato JSON. "
                    "El frontend puede usar estos datos para renderizar detalles adicionales."
                )
            },
            "severity": {
                "help_text": (
                    "Nivel de severidad. "
                    "Valores: `info`, `success`, `warning`, `critical`."
                )
            },
            "link_url": {"help_text": "Deep link opcional hacia la pantalla relevante en el frontend."},
            "sender_name": {"help_text": "Nombre del actor que generó la notificación. Null si es del sistema."},
            "target_scope": {
                "help_text": (
                    "Alcance del destino. Por defecto `individual`. "
                    "El productor puede usar valores personalizados para agrupar notificaciones."
                )
            },
            "target_label": {"help_text": "Etiqueta de agrupación opcional definida por el productor."},
            "status": {
                "help_text": (
                    "Estado de la notificación. "
                    "Valores: `unread` (no leída), `read` (leída), `archived` (archivada)."
                )
            },
            "read_at": {"help_text": "Timestamp del momento en que se marcó como leída. Null si no fue leída."},
            "created_by": {"help_text": "ID del actor que disparó la notificación. Null si es del sistema."},
            "created_at": {"help_text": "Timestamp de creación."},
            "updated_at": {"help_text": "Timestamp de la última modificación."},
        }


class NotificationStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=NotificationStatus.choices,
        help_text=(
            "Nuevo estado de la notificación. "
            "Valores aceptados: `unread` (marcar como no leída), "
            "`read` (marcar como leída), `archived` (archivar)."
        ),
    )


class MarkAllReadRequestSerializer(serializers.Serializer):
    until_id = serializers.IntegerField(
        min_value=1,
        required=False,
        help_text=(
            "Si se proporciona, solo se marcan como leídas las notificaciones "
            "con `id <= until_id`. Si se omite, se marcan todas las no leídas del usuario."
        ),
    )


class BulkMarkReadResponseSerializer(serializers.Serializer):
    updated = serializers.IntegerField(
        help_text="Cantidad de notificaciones marcadas como leídas en esta operación."
    )


class UnreadCountSerializer(serializers.Serializer):
    count = serializers.IntegerField(
        help_text="Cantidad de notificaciones con estado `unread` del usuario autenticado."
    )


