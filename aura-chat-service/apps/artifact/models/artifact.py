from django.db import models

from core.models.base import AuditModel
from core.models.soft_delete import SoftDeleteModel


class Artifact(AuditModel, SoftDeleteModel):
    class Type(models.TextChoices):
        MESSAGE = "MESSAGE", "Message"
        REPORT = "REPORT", "ArtifactReport"
        CHECKLIST = "CHECKLIST", "ArtifactChecklist"
        QUIZ = "QUIZ", "ArtifactQuiz"
        TIMELINE = "TIMELINE", "ArtifactTimeline"
        LESSONS_LEARNED = "LESSONS_LEARNED", "Lessons Learned"
        DECISION_BRIEF = "DECISION_BRIEF", "Decision Brief"

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        FINAL = "final", "Final"
        ARCHIVED = "archived", "Archivado"

    class Mode(models.TextChoices):
        DIRECT = "direct", "Directo"
        RAG = "rag", "Con documentos"

    type = models.CharField(max_length=32, choices=Type.choices)
    title = models.CharField(max_length=500, default="", blank=True)
    description = models.TextField(default="", blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    version = models.IntegerField(default=1)
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.DIRECT)
    fragments = models.JSONField(null=True, blank=True, default=None)
    source_chat = models.ForeignKey(
        "chat.Chat",
        on_delete=models.CASCADE,
        related_name="artifacts",
        db_column="source_chat_id",
    )

    class Meta:
        managed = False
        db_table = "artifact"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.type}] {self.title[:50]}"


class ArtifactVersion(models.Model):
    artifact = models.ForeignKey(
        Artifact,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.IntegerField()
    title = models.CharField(max_length=500)
    description = models.TextField(default="", blank=True)
    status = models.CharField(max_length=16)
    mode = models.CharField(max_length=16, default="direct")
    change_summary = models.TextField(default="", blank=True)
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "artifact_version"
        ordering = ["-version_number"]

    def __str__(self):
        return f"{self.artifact_id} v{self.version_number}"
