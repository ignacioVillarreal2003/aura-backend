"""Modelos de notificaciones (espejos managed=False de tablas de aura_db)."""

from django.db import models
from django.utils import timezone


class NotificationEventType(models.TextChoices):
    CHAT_MEMBER_INVITED = 'apps.chat.member.invited', 'Invitación a chat'
    CHAT_MEMBER_REMOVED = 'apps.chat.member.removed', 'Removido de chat'
    CHAT_LOCKED = 'apps.chat.locked', 'Chat bloqueado'
    AUTH_PASSWORD_CHANGED = 'auth.password.changed', 'Cambio de contraseña'
    AUTH_NEW_LOGIN = 'auth.new_login', 'Nuevo inicio de sesión'
    DOCUMENT_PROCESSING_DONE = 'document.processing.done', 'Documento procesado'
    DOCUMENT_PROCESSING_FAILED = 'document.processing.failed', 'Procesamiento fallido'
    ADMIN_BROADCAST = 'admin.broadcast', 'Mensaje de administrador'


class NotificationSeverity(models.TextChoices):
    INFO = 'info', 'Info'
    SUCCESS = 'success', 'Éxito'
    WARNING = 'warning', 'Advertencia'
    CRITICAL = 'critical', 'Crítica'


class NotificationStatus(models.TextChoices):
    UNREAD = 'unread', 'No leída'
    READ = 'read', 'Leída'


class Notification(models.Model):
    """Espejo de la tabla notification de aura_db."""

    id = models.BigAutoField(primary_key=True)
    receiver_id = models.BigIntegerField(
        db_index=True,
        verbose_name='Receptor (user ID)',
    )
    event_type = models.CharField(
        max_length=128,
        choices=NotificationEventType.choices,
        verbose_name='Tipo de evento',
    )
    message = models.CharField(max_length=500, verbose_name='Mensaje')
    data = models.JSONField(default=dict, blank=True, verbose_name='Datos del evento')
    severity = models.CharField(
        max_length=16,
        choices=NotificationSeverity.choices,
        default=NotificationSeverity.INFO,
        verbose_name='Severidad',
    )
    link_url = models.URLField(max_length=2048, null=True, blank=True, verbose_name='Link')
    actor_name = models.CharField(max_length=255, null=True, blank=True, verbose_name='Actor')
    status = models.CharField(
        max_length=16,
        choices=NotificationStatus.choices,
        default=NotificationStatus.UNREAD,
        verbose_name='Estado',
    )
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='Leída el')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado el')
    created_by = models.BigIntegerField(null=True, blank=True, verbose_name='Creado por (user ID)')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Eliminado el')
    deleted_by = models.BigIntegerField(null=True, blank=True, verbose_name='Eliminado por (user ID)')

    class Meta:
        app_label = 'notifications'
        db_table = 'notification'
        managed = False
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.event_type}] → user:{self.receiver_id} | {self.message[:60]}"

    @property
    def target_scope(self):
        """Alcance del envio del admin (individual o group), guardado en data."""
        return (self.data or {}).get('target_scope')

    @property
    def target_label(self):
        return (self.data or {}).get('target_label')

    def soft_delete(self, deleted_by: int = None):
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(update_fields=['deleted_at', 'deleted_by'])


class IndividualNotification(Notification):
    """Modelo proxy para los envios individuales del admin."""

    class Meta:
        proxy = True
        app_label = 'notifications'
        verbose_name = 'Individual'
        verbose_name_plural = 'Individuales'


class GroupNotification(Notification):
    """Modelo proxy para los envios grupales del admin."""

    class Meta:
        proxy = True
        app_label = 'notifications'
        verbose_name = 'Grupal'
        verbose_name_plural = 'Grupales'
