from django.db import models

from core.models.base import CreatedAuditModel
from core.models.soft_delete import SoftDeleteModel


class ArtifactQuiz(CreatedAuditModel, SoftDeleteModel):
    artifact = models.OneToOneField(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="quiz_content",
        db_column="artifact_id",
    )
    title = models.CharField(max_length=500, default="", blank=True)
    description = models.TextField(default="", blank=True)
    query = models.TextField(default="", blank=True)
    instructions = models.TextField(default="", blank=True)

    class Meta:
        managed = False
        db_table = "artifact_quiz"
        ordering = ["-created_at"]


class ArtifactQuizQuestion(models.Model):
    class Kind(models.TextChoices):
        SINGLE = "single", "Opción única"
        MULTIPLE = "multiple", "Opción múltiple"
        BOOLEAN = "boolean", "Verdadero/Falso"

    quiz = models.ForeignKey(ArtifactQuiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.SINGLE)
    explanation = models.TextField(default="", blank=True)
    selected_option_id = models.BigIntegerField(null=True, blank=True)
    position = models.SmallIntegerField(default=0)
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "artifact_quiz_question"
        ordering = ["position"]


class ArtifactQuizOption(models.Model):
    question = models.ForeignKey(ArtifactQuizQuestion, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    position = models.SmallIntegerField(default=0)
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "artifact_quiz_option"
        ordering = ["position"]
