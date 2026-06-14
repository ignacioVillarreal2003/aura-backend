from django.db import models
from django.utils import timezone

from core.models.soft_delete import SoftDeleteManager


class InboxModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado el")
    created_by = models.BigIntegerField(null=True, blank=True, verbose_name="Creado por")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Eliminado el")
    deleted_by = models.BigIntegerField(null=True, blank=True, verbose_name="Eliminado por")

    objects = SoftDeleteManager()

    class Meta:
        abstract = True

    def soft_delete(self, deleted_by: int | None = None):
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(update_fields=["deleted_at", "deleted_by"])

    def restore(self):
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["deleted_at", "deleted_by"])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
