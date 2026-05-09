from django.db import models
from django.utils import timezone


class AuditedModel(models.Model):
    """Common audit fields shared by every notification table.

    The columns are owned by `sql/schema.sql`; Django manages the rows
    only (`managed = False` in subclass `Meta`).
    """

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado el")
    created_by = models.BigIntegerField(null=True, blank=True, verbose_name="Creado por")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado el")
    updated_by = models.BigIntegerField(null=True, blank=True, verbose_name="Actualizado por")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Eliminado el")
    deleted_by = models.BigIntegerField(null=True, blank=True, verbose_name="Eliminado por")

    class Meta:
        abstract = True

    def soft_delete(self, deleted_by: int | None = None):
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(update_fields=["deleted_at", "deleted_by", "updated_at"])

    def restore(self):
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["deleted_at", "deleted_by", "updated_at"])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
