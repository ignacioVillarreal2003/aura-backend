from django.db import models

from core.models.base import AuditModel
from core.models.soft_delete import SoftDeleteModel


class Assistant(AuditModel, SoftDeleteModel):
    name = models.CharField(max_length=200)
    description = models.TextField(default="")
    system_prompt = models.TextField()
    avatar_emoji = models.CharField(max_length=10, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "assistant"
        ordering = ["name"]
