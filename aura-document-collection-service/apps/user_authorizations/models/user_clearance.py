from django.db import models

from core.models import CreatedAuditModel


class UserClearance(CreatedAuditModel):
    id = models.BigAutoField(primary_key=True)
    user_id = models.BigIntegerField(unique=True)
    classification_level = models.ForeignKey(
        "classification_levels.ClassificationLevel",
        db_column="classification_level_id",
        on_delete=models.DO_NOTHING,
        related_name="user_clearances",
    )

    class Meta:
        managed = False
        db_table = "user_clearance"

    def __str__(self) -> str:
        return f"User {self.user_id} — level {self.classification_level_id}"
