"""
Chat models — managed=False mirrors of tables owned by docker/aura-db/init.sql.
All reads/writes are routed to aura_db via AuraDbRouter.

Cross-DB references (fields pointing to auth_db tables) are stored as plain
BigIntegerField — no SQL FK constraint.
"""

from django.db import models


class Chat(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, verbose_name='Nombre')
    system_prompt = models.TextField(null=True, blank=True, verbose_name='Prompt de sistema')
    response_style = models.TextField(null=True, blank=True, verbose_name='Estilo de respuesta')
    last_message_at = models.DateTimeField(null=True, blank=True, verbose_name='Último mensaje')
    # Cross-DB ref: auth_user.id lives in auth_db; Chat lives in aura_db.
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


class ChatMessage(models.Model):
    id = models.BigAutoField(primary_key=True)
    chat = models.ForeignKey(
        Chat,
        on_delete=models.DO_NOTHING,
        related_name='messages',
        db_column='chat_id',
    )
    message = models.TextField(verbose_name='Mensaje')
    sender_type = models.CharField(max_length=20, verbose_name='Tipo de remitente')
    # Cross-DB ref for sender_type='user'; null for system messages.
    created_by = models.BigIntegerField(null=True, blank=True, verbose_name='Enviado por (user ID)')
    created_at = models.DateTimeField(verbose_name='Enviado el')
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'chat_message'
        app_label = 'chat'
        verbose_name = 'Mensaje'
        verbose_name_plural = 'Mensajes'
        ordering = ['created_at']


class ChatMembership(models.Model):
    id = models.BigAutoField(primary_key=True)
    # Cross-DB ref: auth_user.id lives in auth_db.
    member_id = models.BigIntegerField(verbose_name='Miembro (user ID)')
    chat = models.ForeignKey(
        Chat,
        on_delete=models.DO_NOTHING,
        related_name='memberships',
        db_column='chat_id',
    )
    status = models.CharField(max_length=20, verbose_name='Estado')
    joined_at = models.DateTimeField(null=True, blank=True, verbose_name='Se unió el')
    left_at = models.DateTimeField(null=True, blank=True, verbose_name='Salió el')
    created_by = models.BigIntegerField(verbose_name='Creado por (user ID)')
    created_at = models.DateTimeField(verbose_name='Creado el')
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'chat_membership'
        app_label = 'chat'
        verbose_name = 'Membresía'
        verbose_name_plural = 'Membresías'
