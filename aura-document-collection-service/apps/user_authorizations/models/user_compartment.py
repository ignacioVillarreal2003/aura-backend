from django.db import models

from core.models import CreatedAuditModel


class UserCompartment(CreatedAuditModel):
    id = models.BigAutoField(primary_key=True)
    user_id = models.BigIntegerField()
    compartment = models.ForeignKey(
        "compartments.Compartment",
        db_column="compartment_id",
        on_delete=models.DO_NOTHING,
        related_name="user_compartments",
    )

    class Meta:
        managed = False
        db_table = "user_compartment"
        unique_together = [("user_id", "compartment")]

    def __str__(self) -> str:
        return f"User {self.user_id} — compartment {self.compartment_id}"
