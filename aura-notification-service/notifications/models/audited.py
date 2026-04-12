"""Shared audited base model for notification tables."""

from django.db import models
from django.utils import timezone


class AuditedModel(models.Model):
    """
    Abstract base model with audit and soft-delete fields.
    created_by / updated_by / deleted_by store auth_user.id (BigInt).
    """

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado el',
    )
    created_by = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='Creado por',
        help_text='auth_user.id who created this record',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Actualizado el',
    )
    updated_by = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='Actualizado por',
        help_text='auth_user.id who last updated this record',
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Eliminado el',
        help_text='Soft delete timestamp (null = active)',
    )
    deleted_by = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='Eliminado por',
        help_text='auth_user.id who deleted this record',
    )

    class Meta:
        abstract = True

    def soft_delete(self, deleted_by: int = None):
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(update_fields=['deleted_at', 'deleted_by', 'updated_at'])

    def restore(self):
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['deleted_at', 'deleted_by', 'updated_at'])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
