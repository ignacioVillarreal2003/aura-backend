from django.db import models


class ArtifactBookmark(models.Model):
    artifact = models.ForeignKey(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    user_id = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "artifact_bookmark"
        constraints = [
            models.UniqueConstraint(fields=["artifact", "user_id"], name="uq_artifact_bookmark"),
        ]
        indexes = [
            models.Index(fields=["artifact"], name="idx_artifact_bookmark_artifact"),
            models.Index(fields=["user_id"], name="idx_artifact_bookmark_user"),
        ]
