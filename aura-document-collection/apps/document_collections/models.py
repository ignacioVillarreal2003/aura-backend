from django.db import models


class DocumentCollection(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField()
    updated_by = models.BigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "document_collection"


class UserInDocumentCollection(models.Model):
    id = models.BigAutoField(primary_key=True)
    document_collection = models.ForeignKey(
        DocumentCollection,
        db_column="document_collection_id",
        on_delete=models.DO_NOTHING,
        related_name="user_memberships",
    )
    user_id = models.BigIntegerField()
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField()
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "user_in_document_collection"


class DocumentInDocumentCollection(models.Model):
    id = models.BigAutoField(primary_key=True)
    document_collection = models.ForeignKey(
        DocumentCollection,
        db_column="document_collection_id",
        on_delete=models.DO_NOTHING,
        related_name="document_links",
    )
    document_id = models.BigIntegerField()
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField()
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "document_in_document_collection"


class Document(models.Model):
    """Read-only subset of ``document`` for link validation."""

    id = models.BigAutoField(primary_key=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "document"
