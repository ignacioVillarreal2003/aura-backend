from django.db.models import QuerySet
from django.utils import timezone

from apps.document_collection.models import DocumentInDocumentCollection


class DocumentInDocumentCollectionRepository:
    @staticmethod
    def list_active_by_document_collection_id(document_collection_id: int) -> QuerySet[DocumentInDocumentCollection]:
        return (
            DocumentInDocumentCollection.objects.filter(
                document_collection_id=document_collection_id,
                deleted_at__isnull=True,
            )
            .select_related("document")
            .order_by("id")
        )

    @staticmethod
    def get_active_by_document_collection_id_and_document_id(
        document_collection_id: int,
        document_id: int,
    ) -> DocumentInDocumentCollection | None:
        return (
            DocumentInDocumentCollection.objects.filter(
                document_collection_id=document_collection_id,
                document_id=document_id,
                deleted_at__isnull=True,
            )
            .select_related("document")
            .first()
        )

    @staticmethod
    def get_active_by_id(document_in_document_collection_id: int) -> DocumentInDocumentCollection | None:
        return (
            DocumentInDocumentCollection.objects.filter(
                pk=document_in_document_collection_id,
                deleted_at__isnull=True,
            )
            .select_related("document")
            .first()
        )

    @staticmethod
    def create(
        document_collection_id: int,
        document_id: int,
        created_by: int,
    ) -> DocumentInDocumentCollection:
        now = timezone.now()
        return DocumentInDocumentCollection.objects.create(
            document_collection_id=document_collection_id,
            document_id=document_id,
            created_by=created_by,
            created_at=now,
        )

    @staticmethod
    def soft_delete(document_in_document_collection: DocumentInDocumentCollection, deleted_by: int) -> None:
        document_in_document_collection.deleted_by = deleted_by
        document_in_document_collection.deleted_at = timezone.now()
        document_in_document_collection.save(update_fields=["deleted_by", "deleted_at"])


document_in_document_collection_repository = DocumentInDocumentCollectionRepository()
