from django.db import models

from core.models import CreatedAuditModel, SoftDeleteModel


class UserInDocumentCollection(CreatedAuditModel, SoftDeleteModel):
    id = models.BigAutoField(primary_key=True)
    document_collection = models.ForeignKey(
        "document_collections.DocumentCollection",
        db_column="document_collection_id",
        on_delete=models.DO_NOTHING,
        related_name="user_memberships",
    )
    user_id = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = "user_in_document_collection"

    def __str__(self) -> str:
        return f"User {self.user_id} in collection {self.document_collection_id}"
