from django.db import models

from core.models.base import CreatedAuditModel
from core.models.soft_delete import SoftDeleteModel


class ArtifactDocumentSummary(CreatedAuditModel, SoftDeleteModel):
    artifact = models.OneToOneField(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="document_summary_content",
        db_column="artifact_id",
    )
    title = models.CharField(max_length=500, default="", blank=True)
    description = models.TextField(default="", blank=True)
    summary = models.TextField(default="", blank=True)

    class Meta:
        managed = False
        db_table = "artifact_document_summary"
        ordering = ["-created_at"]
