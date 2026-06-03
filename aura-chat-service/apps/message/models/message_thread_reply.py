from django.db import models


class ArtifactThreadReply(models.Model):
    parent_artifact = models.ForeignKey(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="thread_replies",
    )
    message = models.TextField()
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "artifact_thread_reply"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["parent_artifact"], name="idx_artifact_thread_reply_parent"),
        ]


# Backward-compatible alias
MessageThreadReply = ArtifactThreadReply
