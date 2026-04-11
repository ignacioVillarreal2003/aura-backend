"""Document models for admin visualization.

Both Document and DocumentRole live in aura_db (routed via AuraDbRouter).

Cross-DB references (fields pointing to auth_db tables) are stored as plain
BigIntegerField — no SQL FK constraint, same pattern as receiver_id in notifications:
  - Document.minimum_fau_role_id  → fau_role.id  in auth_db
  - DocumentRole.role_id          → role.id       in auth_db
"""

import uuid
from django.db import models
from accounts.models import AuditedModel


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
    external_document_id = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        verbose_name='ID externo',
        help_text='Identificador del documento en document-processing.',
    )
    external_storage_url = models.CharField(
        max_length=1000,
        blank=True,
        verbose_name='Storage URL externa',
        help_text='Referencia devuelta por document-processing.',
    )
    visible_to_all = models.BooleanField(
        default=False,
        verbose_name='Disponible para todos',
        help_text='Si está activo, el documento queda disponible para todos y no se restringe por grupos ni jerarquía FAU.',
    )
    # Cross-DB reference: fau_role.id lives in auth_db; Document lives in aura_db.
    # Stored as plain BIGINT — no SQL FK constraint.
    minimum_fau_role_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='Rol FAU mínimo',
        help_text='fau_role.id (cross-DB ref to auth_db). Ese rol y los de mayor jerarquía pueden acceder.',
    )

    class Meta:
        db_table = 'documents'
        managed = False
        verbose_name = 'Documento'
        verbose_name_plural = 'Documentos'
        indexes = [
            models.Index(fields=['name'], name='documents_name_7e31f9_idx'),
            models.Index(fields=['deleted_at'], name='documents_deleted_4df53c_idx'),
        ]

    def __str__(self):
        return self.name

    def access_scope_label(self):
        if self.visible_to_all:
            return 'Todos'
        if self.minimum_fau_role_id:
            from accounts.models import FauRole
            fau_role = FauRole.objects.filter(pk=self.minimum_fau_role_id).first()
            name = fau_role.name if fau_role else str(self.minimum_fau_role_id)
            return f'{name} y superiores'
        return 'Restringido'


class DocumentRole(models.Model):
    """Assign documents to roles for access control."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='role_assignments',
        verbose_name='Documento',
    )
    # Cross-DB reference: role.id lives in auth_db; DocumentRole lives in aura_db.
    # Stored as plain BIGINT — no SQL FK constraint.
    role_id = models.BigIntegerField(
        verbose_name='Rol',
        help_text='role.id (cross-DB ref to auth_db)',
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Asignado el',
    )
    assigned_by = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='Asignado por',
        help_text='auth_user.id who assigned this role',
    )

    class Meta:
        db_table = 'document_roles'
        managed = False
        verbose_name = 'Documento por Rol'
        verbose_name_plural = 'Documentos por Rol'
        unique_together = [('document', 'role_id')]
        indexes = [
            models.Index(fields=['document'], name='docrole_doc_50d0b6_idx'),
            models.Index(fields=['role_id'], name='docrole_role_4a3c85_idx'),
        ]

    def __str__(self):
        return f"{self.document.name} → role_id:{self.role_id}"
