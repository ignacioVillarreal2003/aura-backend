from django.db import models

from core.models.base import CreatedAuditModel
from core.models.soft_delete import SoftDeleteModel


class ArtifactChecklist(CreatedAuditModel, SoftDeleteModel):
    artifact = models.OneToOneField(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="checklist_content",
        db_column="artifact_id",
    )
    title = models.CharField(max_length=500, default="", blank=True)
    description = models.TextField(default="", blank=True)
    query = models.TextField(default="", blank=True)

    class Meta:
        managed = False
        db_table = "artifact_checklist"
        ordering = ["-created_at"]


class ArtifactChecklistSection(models.Model):
    checklist = models.ForeignKey(
        ArtifactChecklist,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    title = models.CharField(max_length=200)
    position = models.SmallIntegerField(default=0)
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "artifact_checklist_section"
        ordering = ["position"]


class ArtifactChecklistItem(models.Model):
    section = models.ForeignKey(
        ArtifactChecklistSection,
        on_delete=models.CASCADE,
        related_name="items",
    )
    text = models.CharField(max_length=500)
    is_checked = models.BooleanField(default=False)
    position = models.SmallIntegerField(default=0)
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "artifact_checklist_item"
        ordering = ["position"]
