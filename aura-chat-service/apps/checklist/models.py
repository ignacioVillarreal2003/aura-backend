from django.db import models

from core.models.base import AuditModel
from core.models.soft_delete import SoftDeleteModel


class Checklist(AuditModel, SoftDeleteModel):

    class Mode(models.TextChoices):
        DIRECT = "direct", "Directo"
        RAG = "rag", "Con documentos"

    title = models.CharField(max_length=500)
    mode = models.CharField(max_length=16, choices=Mode.choices)
    source_chat_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "checklist"
        ordering = ["-created_at"]


class ChecklistSection(models.Model):
    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=200)
    position = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "checklist_section"
        ordering = ["position"]


class ChecklistItem(models.Model):
    section = models.ForeignKey(ChecklistSection, on_delete=models.CASCADE, related_name="items")
    text = models.CharField(max_length=500)
    is_checked = models.BooleanField(default=False)
    notes = models.TextField(default="")
    position = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "checklist_item"
        ordering = ["position"]
