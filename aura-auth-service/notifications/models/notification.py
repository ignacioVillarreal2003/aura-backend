"""
Notification models for aura-auth-service admin.

These are managed=False mirrors of tables owned by docker/db/init.sql.
All reads/writes are routed to aura_db via AuraDbRouter.
"""

from django.db import models
from django.utils import timezone


class NotificationType(models.TextChoices):
    SYSTEM = 'system', 'Sistema'
    ADMIN = 'admin', 'Administrador'


class NotificationStatus(models.TextChoices):
    UNREAD = 'unread', 'No leída'
    READ = 'read', 'Leída'
    ARCHIVED = 'archived', 'Archivada'


class Notification(models.Model):
    """
    Mirror of the notification table in aura_db.
    Schema is owned by docker/db/init.sql.
    """

    id = models.BigAutoField(primary_key=True)
    receiver_id = models.BigIntegerField(
        db_index=True,
        verbose_name='Receptor (user ID)',
    )
    message = models.CharField(max_length=500, verbose_name='Mensaje')
    type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        verbose_name='Tipo',
    )
    target_scope = models.CharField(
        max_length=20,
        default='individual',
        verbose_name='Alcance',
    )
    target_label = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Etiqueta de destino',
    )
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.UNREAD,
        verbose_name='Estado',
    )
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='Leída el')
    created_by = models.BigIntegerField(null=True, blank=True, verbose_name='Creado por (user ID)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado el')
    updated_by = models.BigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_by = models.BigIntegerField(null=True, blank=True, verbose_name='Eliminado por (user ID)')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Eliminado el')

    class Meta:
        app_label = 'notifications'
        db_table = 'notification'
        managed = False
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.type}] → user:{self.receiver_id} | {self.message[:60]}"

    def soft_delete(self, deleted_by: int = None):
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(update_fields=['deleted_at', 'deleted_by', 'updated_at'])


class IndividualNotification(Notification):
    """Proxy model for individual notifications in admin."""

    class Meta:
        proxy = True
        app_label = 'notifications'
        verbose_name = 'Individual'
        verbose_name_plural = 'Individuales'


class GroupNotification(Notification):
    """Proxy model for group notifications in admin."""

    class Meta:
        proxy = True
        app_label = 'notifications'
        verbose_name = 'Grupal'
        verbose_name_plural = 'Grupales'


class SystemNotification(Notification):
    """Proxy model for system notifications in admin."""

    class Meta:
        proxy = True
        app_label = 'notifications'
        verbose_name = 'De sistema'
        verbose_name_plural = 'De sistema'
