from django.db import models

from core.models.base import AuditModel
from core.models.soft_delete import SoftDeleteModel


class ArtifactQuiz(AuditModel, SoftDeleteModel):
    artifact = models.OneToOneField(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="quiz_content",
        db_column="artifact_id",
    )
    instructions = models.TextField(default="", blank=True)
    pass_score = models.SmallIntegerField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "artifact_quiz"
        ordering = ["-created_at"]


class ArtifactQuizQuestion(models.Model):
    class Kind(models.TextChoices):
        SINGLE = "single", "Opción única"
        MULTIPLE = "multiple", "Opción múltiple"
        BOOLEAN = "boolean", "Verdadero/Falso"
        OPEN = "open", "Respuesta abierta"

    quiz = models.ForeignKey(ArtifactQuiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.SINGLE)
    explanation = models.TextField(default="", blank=True)
    position = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "artifact_quiz_question"
        ordering = ["position"]


class ArtifactQuizOption(models.Model):
    question = models.ForeignKey(ArtifactQuizQuestion, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    position = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "artifact_quiz_option"
        ordering = ["position"]
