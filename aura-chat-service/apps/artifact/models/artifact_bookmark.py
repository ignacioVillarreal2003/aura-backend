from django.db import models


class ArtifactBookmark(models.Model):
    artifact = models.ForeignKey(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "artifact_bookmark"
        constraints = [
            models.UniqueConstraint(fields=["artifact", "created_by"], name="uq_artifact_bookmark"),
        ]
        indexes = [
            models.Index(fields=["artifact"], name="idx_artifact_bookmark_artifact"),
            models.Index(fields=["created_by"], name="idx_artifact_bookmark_user"),
        ]
