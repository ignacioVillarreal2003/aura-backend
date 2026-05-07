from django.db import models

from core.models import AuditModel, SoftDeleteModel


class DocumentCollection(AuditModel, SoftDeleteModel):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    classification_level = models.ForeignKey(
        "classification_levels.ClassificationLevel",
        db_column="classification_level_id",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="document_collections",
    )
    compartments = models.ManyToManyField(
        "compartments.Compartment",
        through="document_collections.DocumentCollectionCompartment",
        related_name="document_collections",
    )

    class Meta:
        managed = False
        db_table = "document_collection"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name
