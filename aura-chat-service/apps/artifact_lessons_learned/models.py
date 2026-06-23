from django.db import models

from core.models.base import CreatedAuditModel
from core.models.soft_delete import SoftDeleteModel


class ArtifactLessonsLearned(CreatedAuditModel, SoftDeleteModel):
    artifact = models.OneToOneField(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="lessons_learned_content",
        db_column="artifact_id",
    )
    title = models.CharField(max_length=500, default="", blank=True)
    query = models.TextField(default="", blank=True)
    description = models.TextField(default="", blank=True)

    class Meta:
        managed = False
        db_table = "artifact_lessons_learned"
        ordering = ["-created_at"]


class ArtifactLessonsLearnedItem(models.Model):
    class Category(models.TextChoices):
        SUSTAIN = "sustain", "Sostener"
        IMPROVE = "improve", "Mejorar"
        RECOMMENDATION = "recommendation", "Recomendación"

    lessons_learned = models.ForeignKey(
        ArtifactLessonsLearned,
        on_delete=models.CASCADE,
        related_name="items",
    )
    category = models.CharField(max_length=16, choices=Category.choices)
    observation = models.TextField()
    discussion = models.TextField(default="", blank=True)
    recommendation = models.TextField(default="", blank=True)
    position = models.SmallIntegerField(default=0)
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "artifact_lessons_learned_item"
        ordering = ["position"]
