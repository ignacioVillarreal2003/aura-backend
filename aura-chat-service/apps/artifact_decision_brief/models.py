from django.db import models

from core.models.base import CreatedAuditModel
from core.models.soft_delete import SoftDeleteModel


class ArtifactDecisionBrief(CreatedAuditModel, SoftDeleteModel):
    artifact = models.OneToOneField(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="decision_brief_content",
        db_column="artifact_id",
    )
    title = models.CharField(max_length=500, default="", blank=True)
    query = models.TextField(default="", blank=True)
    description = models.TextField(default="", blank=True)
    context = models.TextField(default="", blank=True)
    risks = models.TextField(default="", blank=True)
    recommendation = models.TextField(default="", blank=True)

    class Meta:
        managed = False
        db_table = "artifact_decision_brief"
        ordering = ["-created_at"]


class ArtifactDecisionBriefOption(models.Model):
    decision_brief = models.ForeignKey(
        ArtifactDecisionBrief,
        on_delete=models.CASCADE,
        related_name="options",
    )
    title = models.CharField(max_length=300)
    pros = models.TextField(default="", blank=True)
    cons = models.TextField(default="", blank=True)
    is_recommended = models.BooleanField(default=False)
    position = models.SmallIntegerField(default=0)
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "artifact_decision_brief_option"
        ordering = ["position"]
