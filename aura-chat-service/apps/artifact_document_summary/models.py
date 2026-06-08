from django.db import models

from core.models.base import AuditModel
from core.models.soft_delete import SoftDeleteModel


class ArtifactDocumentSummary(AuditModel, SoftDeleteModel):
    artifact = models.OneToOneField(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="document_summary_content",
        db_column="artifact_id",
    )
    document_ids = models.JSONField(default=list)
    summary = models.TextField(default="", blank=True)

    class Meta:
        managed = False
        db_table = "artifact_document_summary"
        ordering = ["-created_at"]
