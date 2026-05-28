from django.db import models

from core.models.base import AuditModel
from core.models.soft_delete import SoftDeleteModel


class Checklist(AuditModel, SoftDeleteModel):

    class Mode(models.TextChoices):
        DIRECT = "direct", "Directo"
        RAG = "rag", "Con documentos"

    title = models.CharField(max_length=500)
    items = models.JSONField(default=list)
    mode = models.CharField(max_length=16, choices=Mode.choices)
    metadata = models.JSONField(default=dict)

    class Meta:
        managed = False
        db_table = "checklist"
        ordering = ["-created_at"]
