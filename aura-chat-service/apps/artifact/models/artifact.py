from django.db import models

from core.models.base import AuditModel
from core.models.soft_delete import SoftDeleteModel


class Artifact(AuditModel, SoftDeleteModel):
    class Type(models.TextChoices):
        MESSAGE = "MESSAGE", "Mensaje"
        REPORT = "REPORT", "Informe"
        CHECKLIST = "CHECKLIST", "Checklist"
        QUIZ = "QUIZ", "Cuestionario"
        TIMELINE = "TIMELINE", "Línea de tiempo"
        LESSONS_LEARNED = "LESSONS_LEARNED", "Lecciones aprendidas"
        DECISION_BRIEF = "DECISION_BRIEF", "Brief de decisión"
        DOCUMENT_SUMMARY = "DOCUMENT_SUMMARY", "Resumen de documento"
        DOCUMENT_ACTION = "DOCUMENT_ACTION", "Acción sobre documento"

    type = models.CharField(max_length=32, choices=Type.choices)
    retrieve_context = models.BooleanField(null=True, blank=True, default=None)
    process_documents = models.BooleanField(null=True, blank=True, default=None)
    document_ids = models.JSONField(blank=True, default=list)
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
