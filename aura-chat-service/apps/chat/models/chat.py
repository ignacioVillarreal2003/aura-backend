from django.db import models

from core.models import AuditModel, SoftDeleteModel


class Chat(AuditModel, SoftDeleteModel):
    name = models.CharField(max_length=255)
    system_prompt = models.TextField(null=True, blank=True)
    response_style = models.TextField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "chat"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
