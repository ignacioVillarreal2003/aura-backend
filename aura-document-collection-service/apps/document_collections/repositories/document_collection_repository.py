from django.db.models import QuerySet
from django.utils import timezone

from apps.document_collections.models import DocumentCollection


class DocumentCollectionRepository:
    def get_active_by_id(self, document_collection_id: int) -> DocumentCollection | None:
        return DocumentCollection.objects.filter(pk=document_collection_id).first()

    def list_active(self) -> QuerySet[DocumentCollection]:
        return DocumentCollection.objects.all().order_by("-created_at")

    def create(self, name: str, created_by: int) -> DocumentCollection:
        return DocumentCollection.objects.create(
            name=name,
            created_by=created_by,
        )

    def update(self, document_collection: DocumentCollection, name: str, updated_by: int) -> DocumentCollection:
        document_collection.name = name
        document_collection.updated_by = updated_by
        document_collection.updated_at = timezone.now()
        document_collection.save(update_fields=["name", "updated_by", "updated_at"])
        return document_collection

    def soft_delete(self, document_collection: DocumentCollection, deleted_by: int) -> None:
        document_collection.delete(deleted_by=deleted_by)


document_collection_repository = DocumentCollectionRepository()
