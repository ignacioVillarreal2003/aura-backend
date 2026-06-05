from django.db import models

from core.models.base import AuditModel
from core.models.soft_delete import SoftDeleteModel


class ArtifactDecisionBrief(AuditModel, SoftDeleteModel):
    artifact = models.OneToOneField(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="decision_brief_content",
        db_column="artifact_id",
    )
    problem = models.TextField(default="", blank=True)
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
    description = models.TextField(default="", blank=True)
    pros = models.TextField(default="", blank=True)
    cons = models.TextField(default="", blank=True)
    is_recommended = models.BooleanField(default=False)
    position = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "artifact_decision_brief_option"
        ordering = ["position"]


