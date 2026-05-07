from django.db import models

from core.models import CreatedAuditModel


class DocumentCollectionCompartment(CreatedAuditModel):
    id = models.BigAutoField(primary_key=True)
    document_collection = models.ForeignKey(
        "document_collections.DocumentCollection",
        db_column="document_collection_id",
        on_delete=models.DO_NOTHING,
        related_name="collection_compartments",
    )
    compartment = models.ForeignKey(
        "compartments.Compartment",
        db_column="compartment_id",
        on_delete=models.DO_NOTHING,
        related_name="collection_compartments",
    )

    class Meta:
        managed = False
        db_table = "document_collection_compartment"
        unique_together = [("document_collection", "compartment")]

    def __str__(self) -> str:
        return f"Collection {self.document_collection_id} — compartment {self.compartment_id}"
