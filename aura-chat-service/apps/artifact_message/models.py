from django.db import models

from apps.artifact.models.artifact import Artifact
from core.models.soft_delete import SoftDeleteModel


class ArtifactMessage(SoftDeleteModel):
    class SenderType(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    artifact = models.OneToOneField(
        Artifact,
        on_delete=models.CASCADE,
        related_name="message_content",
    )
    message = models.TextField(max_length=10000)
    sender_type = models.CharField(max_length=16, choices=SenderType.choices)
    created_by = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "artifact_message"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.sender_type}] {self.message[:50]}"
