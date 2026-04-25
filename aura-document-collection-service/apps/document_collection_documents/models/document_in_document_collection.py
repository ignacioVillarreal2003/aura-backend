from django.db import models

from core.models import CreatedAuditModel, SoftDeleteModel


class DocumentInDocumentCollection(CreatedAuditModel, SoftDeleteModel):
    id = models.BigAutoField(primary_key=True)
    document_collection = models.ForeignKey(
        "document_collections.DocumentCollection",
        db_column="document_collection_id",
        on_delete=models.DO_NOTHING,
        related_name="document_links",
    )
    document = models.ForeignKey(
        "document_collection_documents.Document",
        db_column="document_id",
        on_delete=models.DO_NOTHING,
        related_name="collection_links",
    )

    class Meta:
        managed = False
        db_table = "document_in_document_collection"

    def __str__(self) -> str:
        return f"Document {self.document_id} in collection {self.document_collection_id}"
