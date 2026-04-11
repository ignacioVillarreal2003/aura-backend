"""Custom grouping models for accounts."""

import uuid
from django.db import models
from accounts.models.audited import AuditedModel


class CustomGroup(AuditedModel):
    """Custom group model detached from permissions."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
        verbose_name='Nombre',
    )
    description = models.TextField(
        blank=True,
        verbose_name='Descripción',
    )
    documents = models.ManyToManyField(
        'documents.Document',
        blank=True,
        related_name='groups',
        verbose_name='Documentos',
    )

    class Meta:
        db_table = 'custom_groups'
        managed = False
        verbose_name = 'Grupo'
        verbose_name_plural = 'Grupos'
        indexes = [
            models.Index(fields=['name'], name='custom_gro_name_8c5f90_idx'),
            models.Index(fields=['deleted_at'], name='custom_gro_deleted_2b06a5_idx'),
        ]

    def __str__(self):
        return self.name
