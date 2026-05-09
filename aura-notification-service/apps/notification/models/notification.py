"""In-app notification record.

Mirror of the `notification` table owned by `sql/schema.sql`.
`receiver_id` and audit `*_by` columns reference `auth_user.id`
(cross-service, no FK constraint).
"""

from django.db import models
from django.utils import timezone

from apps.notification.models.audited import AuditedModel


class NotificationType(models.TextChoices):
    SYSTEM = "system", "Sistema"
    ADMIN = "admin", "Administrador"
    USER = "user", "Usuario"
    EVENT = "event", "Evento"


class NotificationStatus(models.TextChoices):
    UNREAD = "unread", "No leida"
    READ = "read", "Leida"
    ARCHIVED = "archived", "Archivada"


class NotificationSeverity(models.TextChoices):
    INFO = "info", "Info"
    SUCCESS = "success", "Success"
    WARNING = "warning", "Warning"
    CRITICAL = "critical", "Critical"


class Notification(AuditedModel):
    id = models.BigAutoField(primary_key=True)
    receiver_id = models.BigIntegerField(db_index=True, verbose_name="Receptor")

    message = models.CharField(max_length=500, verbose_name="Mensaje")

    type = models.CharField(
        max_length=64,
        default=NotificationType.SYSTEM,
        verbose_name="Tipo",
    )

    event_type = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        verbose_name="Tipo de evento",
        help_text="Identifier from the event registry (e.g. chat.member.invited).",
    )

    event_key = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        verbose_name="Idempotency key",
        help_text="Optional unique key per receiver to deduplicate retries.",
    )

    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Payload",
        help_text="Original event context kept for the frontend.",
    )

    target_scope = models.CharField(
        max_length=64,
        default="individual",
        db_index=True,
        verbose_name="Alcance",
    )

    target_label = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Etiqueta de destino",
    )

    sender_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Nombre del emisor",
    )

    severity = models.CharField(
        max_length=16,
        choices=NotificationSeverity.choices,
        default=NotificationSeverity.INFO,
        verbose_name="Severidad",
    )

    link_url = models.TextField(null=True, blank=True, verbose_name="Link")

    status = models.CharField(
        max_length=64,
        choices=NotificationStatus.choices,
        default=NotificationStatus.UNREAD,
        db_index=True,
        verbose_name="Estado",
    )

    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Leida el")

    class Meta:
        db_table = "notification"
        managed = False
        verbose_name = "Notificacion"
        verbose_name_plural = "Notificaciones"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.event_type or self.type}] -> user:{self.receiver_id} | {self.message[:60]}"

    def mark_read(self, updated_by: int | None = None):
        self.status = NotificationStatus.READ
        self.read_at = timezone.now()
        self.updated_by = updated_by
        self.save(update_fields=["status", "read_at", "updated_by", "updated_at"])

    def mark_unread(self, updated_by: int | None = None):
        self.status = NotificationStatus.UNREAD
        self.read_at = None
        self.updated_by = updated_by
        self.save(update_fields=["status", "read_at", "updated_by", "updated_at"])

    def archive(self, updated_by: int | None = None):
        self.status = NotificationStatus.ARCHIVED
        self.updated_by = updated_by
        self.save(update_fields=["status", "updated_by", "updated_at"])
