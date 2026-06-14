from django.db import models
from django.utils import timezone

from apps.notification.models.audited import InboxModel


class NotificationStatus(models.TextChoices):
    UNREAD = "unread", "No leida"
    READ = "read", "Leida"


class NotificationSeverity(models.TextChoices):
    INFO = "info", "Info"
    SUCCESS = "success", "Success"
    WARNING = "warning", "Warning"
    CRITICAL = "critical", "Critical"


class Notification(InboxModel):
    id = models.BigAutoField(primary_key=True)
    receiver_id = models.BigIntegerField(db_index=True, verbose_name="Receptor")
    event_type = models.CharField(max_length=128, verbose_name="Tipo de evento")
    message = models.CharField(max_length=500, verbose_name="Mensaje")
    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Payload",
        help_text="Original event context kept for the frontend.",
    )
    severity = models.CharField(
        max_length=16,
        choices=NotificationSeverity.choices,
        default=NotificationSeverity.INFO,
        verbose_name="Severidad",
    )
    link_url = models.URLField(max_length=2048, null=True, blank=True, verbose_name="Link")
    actor_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Nombre del actor",
    )
    status = models.CharField(
        max_length=16,
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
        return f"[{self.event_type}] -> user:{self.receiver_id} | {self.message[:60]}"

    def mark_read(self):
        self.status = NotificationStatus.READ
        self.read_at = timezone.now()
        self.save(update_fields=["status", "read_at"])

    def mark_unread(self):
        self.status = NotificationStatus.UNREAD
        self.read_at = None
        self.save(update_fields=["status", "read_at"])
