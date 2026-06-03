from django.db import models

from core.models.base import AuditModel
from core.models.soft_delete import SoftDeleteModel


class DecisionBrief(AuditModel, SoftDeleteModel):
    class Mode(models.TextChoices):
        DIRECT = "direct", "Directo"
        RAG = "rag", "Con documentos"

    title = models.CharField(max_length=500)
    problem = models.TextField(default="", blank=True)
    context = models.TextField(default="", blank=True)
    risks = models.TextField(default="", blank=True)
    recommendation = models.TextField(default="", blank=True)
    mode = models.CharField(max_length=16, choices=Mode.choices)
    source_chat_id = models.BigIntegerField(null=True, blank=True)
    artifact_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "decision_brief"
        ordering = ["-created_at"]


class DecisionBriefOption(models.Model):
    decision_brief = models.ForeignKey(DecisionBrief, on_delete=models.CASCADE, related_name="options")
    title = models.CharField(max_length=300)
    description = models.TextField(default="", blank=True)
    pros = models.TextField(default="", blank=True)
    cons = models.TextField(default="", blank=True)
    is_recommended = models.BooleanField(default=False)
    position = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "decision_brief_option"
        ordering = ["position"]
