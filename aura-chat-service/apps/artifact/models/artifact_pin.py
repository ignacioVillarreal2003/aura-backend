from django.db import models


class ArtifactPin(models.Model):
    artifact = models.ForeignKey(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="pins",
    )
    chat = models.ForeignKey(
        "chat.Chat",
        on_delete=models.CASCADE,
        related_name="pinned_artifacts",
    )
    pinned_by = models.BigIntegerField()
    pinned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "artifact_pin"
        constraints = [
            models.UniqueConstraint(fields=["artifact", "chat"], name="artifact_pin_unique"),
        ]
        indexes = [
            models.Index(fields=["chat"], name="idx_artifact_pin_chat"),
            models.Index(fields=["artifact"], name="idx_artifact_pin_artifact"),
        ]

    def __str__(self):
        return f"Pinned artifact {self.artifact_id} in chat {self.chat_id}"
