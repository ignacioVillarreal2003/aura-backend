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
        DOCUMENT_SUMMARY = "DOCUMENT_SUMMARY", "Document Summary"
        DOCUMENT_ACTION = "DOCUMENT_ACTION", "Document Action"

    class Mode(models.TextChoices):
        DIRECT = "direct", "Directo"
        RAG = "rag", "Con documentos"

    type = models.CharField(max_length=32, choices=Type.choices)
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
        return f"[{self.type}] artifact:{self.id}"
