"""Notification model."""

from django.db import models
from django.utils import timezone
from notifications.models.audited import AuditedModel


class NotificationType(models.TextChoices):
    SYSTEM = 'system', 'Sistema'
    ADMIN = 'admin', 'Administrador'
    USER = 'user', 'Usuario'


class NotificationStatus(models.TextChoices):
    UNREAD = 'unread', 'No leída'
    READ = 'read', 'Leída'
    ARCHIVED = 'archived', 'Archivada'


class Notification(AuditedModel):
    """
    In-app notification record.
    receiver_id references auth_user.id (cross-service, no FK constraint).
    """

    id = models.BigAutoField(primary_key=True)
    receiver_id = models.BigIntegerField(
        db_index=True,
        verbose_name='Receptor',
        help_text='auth_user.id of the notification recipient',
    )
    message = models.CharField(
        max_length=500,
        verbose_name='Mensaje',
    )
    type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        verbose_name='Tipo',
    )
    target_scope = models.CharField(
        max_length=20,
        default='individual',
        db_index=True,
        verbose_name='Alcance',
        help_text='individual, group, system',
    )
    target_label = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Etiqueta de destino',
        help_text='Optional source label (group or role names)',
    )
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.UNREAD,
        verbose_name='Estado',
        db_index=True,
    )
    sender_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Nombre del emisor',
        help_text='Display name of the sender at the time of creation (denormalized)',
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Leída el',
        help_text='Timestamp when status was set to read',
    )

    class Meta:
        db_table = 'notification'
        managed = False
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        indexes = [
            models.Index(fields=['receiver_id', 'status'], name='notif_receiver_status_idx'),
            models.Index(fields=['deleted_at'], name='notif_deleted_at_idx'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.type}] → user:{self.receiver_id} | {self.message[:60]}"

    def mark_read(self, updated_by: int = None):
        self.status = NotificationStatus.READ
        self.read_at = timezone.now()
        self.updated_by = updated_by
        self.save(update_fields=['status', 'read_at', 'updated_by', 'updated_at'])

    def archive(self, updated_by: int = None):
        self.status = NotificationStatus.ARCHIVED
        self.updated_by = updated_by
        self.save(update_fields=['status', 'updated_by', 'updated_at'])
