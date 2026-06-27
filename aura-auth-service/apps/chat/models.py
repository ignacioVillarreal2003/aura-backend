"""Modelos de chat (espejos managed=False de tablas de aura_db)."""

from django.db import models


class Chat(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, verbose_name='Nombre')
    system_prompt = models.TextField(null=True, blank=True, verbose_name='Prompt de sistema')
    response_style = models.TextField(null=True, blank=True, verbose_name='Estilo de respuesta')
    last_message_at = models.DateTimeField(null=True, blank=True, verbose_name='Último mensaje')
    # Referencia a auth_user.id, que vive en la otra base
    created_by = models.BigIntegerField(verbose_name='Creado por (user ID)')
    created_at = models.DateTimeField(verbose_name='Creado el')
    updated_by = models.BigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Eliminado el')

    class Meta:
        managed = False
        db_table = 'chat'
        app_label = 'chat'
        verbose_name = 'Chat'
        verbose_name_plural = 'Chats'
        ordering = ['-created_at']

    def __str__(self):
        return f'#{self.id} — {self.name}'


class ArtifactMessage(models.Model):
    """Espejo de artifact_message: un registro por mensaje."""
    id = models.BigAutoField(primary_key=True)
    artifact_id = models.BigIntegerField()
    message = models.TextField(verbose_name='Mensaje')
    sender_type = models.CharField(max_length=16, verbose_name='Tipo de remitente')
    created_by = models.BigIntegerField(null=True, blank=True, verbose_name='Enviado por (user ID)')
    created_at = models.DateTimeField(verbose_name='Enviado el')
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'artifact_message'
        app_label = 'chat'
        verbose_name = 'Mensaje'
        verbose_name_plural = 'Mensajes'
        ordering = ['created_at']
