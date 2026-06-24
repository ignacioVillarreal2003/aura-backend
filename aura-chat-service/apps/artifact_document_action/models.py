from django.db import models

from core.models.base import CreatedAuditModel
from core.models.soft_delete import SoftDeleteModel


class ArtifactDocumentAction(CreatedAuditModel, SoftDeleteModel):
    artifact = models.OneToOneField(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="document_action_content",
        db_column="artifact_id",
    )
    title = models.CharField(max_length=500, default="", blank=True)
    description = models.TextField(default="", blank=True)
    instruction = models.TextField(default="", blank=True)
    action = models.CharField(max_length=32, null=True, blank=True)
    result = models.TextField(default="", blank=True)

    class Meta:
        managed = False
        db_table = "artifact_document_action"
        ordering = ["-created_at"]
