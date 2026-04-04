"""Document models for admin visualization."""

import uuid
from django.db import models
from accounts.models import AuditedModel, Role


class Document(AuditedModel):
    """Document metadata for admin listing."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name='Nombre',
        help_text='Nombre del documento',
    )
    description = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text='Descripción opcional',
    )
    size_bytes = models.PositiveBigIntegerField(
        default=0,
        verbose_name='Tamaño (bytes)',
        help_text='Tamaño del archivo en bytes',
    )

    class Meta:
        db_table = 'documents'
        verbose_name = 'Documento'
        verbose_name_plural = 'Documentos'
        indexes = [
            models.Index(fields=['name'], name='documents_name_7e31f9_idx'),
            models.Index(fields=['deleted_at'], name='documents_deleted_4df53c_idx'),
        ]

    def __str__(self):
        return self.name


class DocumentRole(models.Model):
    """Assign documents to roles for admin visualization."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='role_assignments',
        verbose_name='Documento',
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='document_assignments',
        verbose_name='Rol',
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Asignado el',
    )
    assigned_by = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Asignado por',
    )

    class Meta:
        db_table = 'document_roles'
        verbose_name = 'Documento por Rol'
        verbose_name_plural = 'Documentos por Rol'
        unique_together = [('document', 'role')]
        indexes = [
            models.Index(fields=['document'], name='docrole_doc_50d0b6_idx'),
            models.Index(fields=['role'], name='docrole_role_4a3c85_idx'),
        ]

    def __str__(self):
        return f"{self.document.name} -> {self.role.name}"
