"""Modelos de tokens del servicio de autenticacion."""

import uuid
from django.db import models
from apps.accounts.models.audited import AuditedModel
from apps.accounts.models.user import User


class RefreshToken(AuditedModel):
    """Tabla de refresh tokens de las sesiones."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        verbose_name='Token',
        help_text="Unique refresh token value (UUID)",
    )
    is_revoked = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Revocado',
        help_text="Whether this token has been revoked",
    )
    expires_at = models.DateTimeField(
        verbose_name='Expira el',
        help_text="Token expiration timestamp",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='Dirección IP',
        help_text="Client IP address when token was issued",
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name='User Agent',
        help_text="Client User-Agent when token was issued",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='refresh_tokens',
        verbose_name='Usuario',
        help_text="User who owns this refresh token",
    )

    class Meta:
        db_table = 'refresh_tokens'
        managed = False
        verbose_name = 'Token de Refresco'
        verbose_name_plural = 'Tokens de Refresco'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['token']),
            models.Index(fields=['is_revoked']),
            models.Index(fields=['expires_at']),
        ]
