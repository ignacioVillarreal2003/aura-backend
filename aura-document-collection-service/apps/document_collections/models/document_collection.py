from django.db import models

from core.models import AuditModel, SoftDeleteModel


class DocumentCollection(AuditModel, SoftDeleteModel):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = "document_collection"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name
