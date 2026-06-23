from django.db import models

from core.models.base import CreatedAuditModel
from core.models.soft_delete import SoftDeleteModel


class ArtifactTimeline(CreatedAuditModel, SoftDeleteModel):
    artifact = models.OneToOneField(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="timeline_content",
        db_column="artifact_id",
    )
    title = models.CharField(max_length=500, default="", blank=True)
    query = models.TextField(default="", blank=True)
    description = models.TextField(default="", blank=True)

    class Meta:
        managed = False
        db_table = "artifact_timeline"
        ordering = ["-created_at"]


class ArtifactTimelineEvent(models.Model):
    timeline = models.ForeignKey(ArtifactTimeline, on_delete=models.CASCADE, related_name="events")
    title = models.CharField(max_length=300)
    description = models.TextField(default="", blank=True)
    occurred_label = models.CharField(max_length=100, default="", blank=True)
    position = models.SmallIntegerField(default=0)
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "artifact_timeline_event"
        ordering = ["position"]
