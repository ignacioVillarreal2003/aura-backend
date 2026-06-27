"""Modelo Document, mapeado a la tabla document de aura_db."""

from django.db import models
from django.utils import timezone


class Document(models.Model):
    id = models.BigAutoField(primary_key=True)
    # Tiene valor solo en documentos que un usuario subio dentro de un chat
    # (privados); los de admin/coleccion lo tienen en NULL
    chat_id = models.BigIntegerField(null=True, blank=True, verbose_name='Chat')
    name = models.CharField(max_length=255, verbose_name='Nombre')
    description = models.TextField(blank=True, verbose_name='Descripción')
    file_size_bytes = models.BigIntegerField(default=0, verbose_name='Tamaño (bytes)')
    storage_url = models.CharField(max_length=255, blank=True, verbose_name='Storage URL')
    status = models.CharField(max_length=64, blank=True, verbose_name='Estado')
    mime_type = models.CharField(max_length=64, blank=True, verbose_name='Tipo MIME')
    created_by = models.BigIntegerField(null=True, blank=True, verbose_name='Creado por')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado el')
    updated_by = models.BigIntegerField(null=True, blank=True, verbose_name='Actualizado por')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizado el')
    deleted_by = models.BigIntegerField(null=True, blank=True, verbose_name='Eliminado por')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Eliminado el')

    class Meta:
        db_table = 'document'
        managed = False
        verbose_name = 'Documento'
        verbose_name_plural = 'Documentos'

    def __str__(self):
        return self.name

    def soft_delete(self, deleted_by=None):
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(update_fields=['deleted_at', 'deleted_by', 'updated_at'])

    @property
    def is_deleted(self):
        return self.deleted_at is not None
