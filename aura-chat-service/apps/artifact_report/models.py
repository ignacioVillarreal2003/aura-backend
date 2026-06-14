from django.db import models

from core.models.base import CreatedAuditModel
from core.models.soft_delete import SoftDeleteModel


class ArtifactReport(CreatedAuditModel, SoftDeleteModel):
    class Type(models.TextChoices):
        SITREP = "SITREP", "SITREP"
        INTSUM = "INTSUM", "INTSUM"
        OPORD = "OPORD", "OPORD"

    artifact = models.OneToOneField(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="report_content",
        db_column="artifact_id",
    )
    type = models.CharField(max_length=16, choices=Type.choices)
    title = models.CharField(max_length=500, default="", blank=True)
    description = models.TextField(default="", blank=True)
    query = models.TextField(default="", blank=True)
    content = models.TextField()

    class Meta:
        managed = False
        db_table = "artifact_report"
        ordering = ["-created_at"]
