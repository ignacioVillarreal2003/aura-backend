from django.db import models


class ArtifactPin(models.Model):
    artifact = models.ForeignKey(
        "artifact.Artifact",
        on_delete=models.CASCADE,
        related_name="pins",
    )
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "artifact_pin"
        constraints = [
            models.UniqueConstraint(fields=["artifact"], name="artifact_pin_unique"),
        ]
        indexes = [
            models.Index(fields=["artifact"], name="idx_artifact_pin_artifact"),
            models.Index(fields=["created_by"], name="idx_artifact_pin_user"),
        ]

    def __str__(self):
        return f"Pinned artifact {self.artifact_id} by user {self.created_by}"
