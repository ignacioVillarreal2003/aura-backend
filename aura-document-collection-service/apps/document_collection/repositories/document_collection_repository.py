from django.db.models import QuerySet
from django.utils import timezone

from apps.document_collection.models import DocumentCollection


class DocumentCollectionRepository:
    @staticmethod
    def get_active_by_id(document_collection_id: int) -> DocumentCollection | None:
        return DocumentCollection.objects.filter(pk=document_collection_id, deleted_at__isnull=True).first()

    @staticmethod
    def list_active() -> QuerySet[DocumentCollection]:
        return DocumentCollection.objects.filter(deleted_at__isnull=True).order_by("-created_at")

    @staticmethod
    def create(name: str, created_by: int) -> DocumentCollection:
        return DocumentCollection.objects.create(
            name=name,
            created_by=created_by,
            created_at=timezone.now(),
        )

    @staticmethod
    def update(document_collection: DocumentCollection, name: str, updated_by: int) -> DocumentCollection:
        document_collection.name = name
        document_collection.updated_by = updated_by
        document_collection.updated_at = timezone.now()
        document_collection.save(update_fields=["name", "updated_by", "updated_at"])
        return document_collection

    @staticmethod
    def soft_delete(document_collection: DocumentCollection, deleted_by: int) -> None:
        document_collection.deleted_by = deleted_by
        document_collection.deleted_at = timezone.now()
        document_collection.save(update_fields=["deleted_by", "deleted_at"])


document_collection_repository = DocumentCollectionRepository()
