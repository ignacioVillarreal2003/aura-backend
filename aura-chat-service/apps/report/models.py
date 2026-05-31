from django.db import models

from core.models.base import AuditModel
from core.models.soft_delete import SoftDeleteModel


class Report(AuditModel, SoftDeleteModel):
    class Type(models.TextChoices):
        SITREP = "SITREP", "SITREP"
        INTSUM = "INTSUM", "INTSUM"
        OPORD = "OPORD", "OPORD"

    class Mode(models.TextChoices):
        DIRECT = "direct", "Directo"
        RAG = "rag", "Con documentos"

    type = models.CharField(max_length=16, choices=Type.choices)
    title = models.CharField(max_length=500)
    content = models.TextField()
    mode = models.CharField(max_length=16, choices=Mode.choices)
    source_chat_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "report"
        ordering = ["-created_at"]
