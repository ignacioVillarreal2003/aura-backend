from django.db import models

from core.models.base import AuditModel
from core.models.soft_delete import SoftDeleteModel


class Assistant(AuditModel, SoftDeleteModel):
    name = models.CharField(max_length=256)
    description = models.TextField(default="")
    system_prompt = models.TextField()
    response_style = models.TextField(default="", blank=True)
    avatar_emoji = models.CharField(max_length=16, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "assistant"
        ordering = ["name"]
