from django.db import models

from core.models.base import AuditModel
from core.models.soft_delete import SoftDeleteModel


class ArtifactReport(AuditModel, SoftDeleteModel):
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
    content = models.TextField()

    class Meta:
        managed = False
        db_table = "artifact_report"
        ordering = ["-created_at"]


# Backward-compatible alias
Report = ArtifactReport
