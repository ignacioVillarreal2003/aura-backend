from django.db import models

from core.models import AuditModel, SoftDeleteModel


class ArtifactThreadReply(AuditModel, SoftDeleteModel):
    parent_artifact = models.ForeignKey(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="thread_replies",
    )
    message = models.TextField()

    class Meta:
        managed = False
        db_table = "artifact_thread_reply"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["parent_artifact"], name="idx_art_thrd_reply_par"),
            models.Index(fields=["deleted_at"], name="idx_art_thrd_reply_del"),
        ]
