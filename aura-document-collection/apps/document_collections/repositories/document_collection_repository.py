from django.db.models import QuerySet
from django.utils import timezone

from apps.document_collections.models import DocumentCollection, UserInDocumentCollection


class DocumentCollectionRepository:
    def get_active_readonly(self, pk: int) -> DocumentCollection | None:
        return DocumentCollection.objects.filter(pk=pk, deleted_at__isnull=True).first()

    def list_for_user(self, user_id: int) -> QuerySet[DocumentCollection]:
        return (
            DocumentCollection.objects.filter(
                deleted_at__isnull=True,
                id__in=UserInDocumentCollection.objects.filter(
                    user_id=user_id,
                    deleted_at__isnull=True,
                ).values_list("document_collection_id", flat=True),
            )
            .order_by("-created_at")
        )

    def create(self, *, name: str, created_by: int) -> DocumentCollection:
        now = timezone.now()
        return DocumentCollection.objects.create(
            name=name,
            created_by=created_by,
            created_at=now,
        )

    def update_name(self, collection: DocumentCollection, *, name: str, updated_by: int) -> DocumentCollection:
        now = timezone.now()
        collection.name = name
        collection.updated_by = updated_by
        collection.updated_at = now
        collection.save(update_fields=["name", "updated_by", "updated_at"])
        return collection

    def soft_delete(self, collection: DocumentCollection, *, deleted_by: int) -> None:
        now = timezone.now()
        collection.deleted_by = deleted_by
        collection.deleted_at = now
        collection.save(update_fields=["deleted_by", "deleted_at"])


document_collection_repository = DocumentCollectionRepository()
