from django.db.models import QuerySet
from django.utils import timezone

from apps.document_collections.models import DocumentInDocumentCollection


class DocumentLinkRepository:
    def list_active(self, collection_id: int) -> QuerySet[DocumentInDocumentCollection]:
        return (
            DocumentInDocumentCollection.objects.filter(
                document_collection_id=collection_id,
                deleted_at__isnull=True,
            )
            .order_by("id")
        )

    def get_active(self, *, collection_id: int, link_id: int) -> DocumentInDocumentCollection | None:
        return DocumentInDocumentCollection.objects.filter(
            pk=link_id,
            document_collection_id=collection_id,
            deleted_at__isnull=True,
        ).first()

    def create(
        self,
        *,
        collection_id: int,
        document_id: int,
        created_by: int,
    ) -> DocumentInDocumentCollection:
        now = timezone.now()
        return DocumentInDocumentCollection.objects.create(
            document_collection_id=collection_id,
            document_id=document_id,
            created_by=created_by,
            created_at=now,
        )

    def soft_delete(self, link: DocumentInDocumentCollection, *, deleted_by: int) -> None:
        now = timezone.now()
        link.deleted_by = deleted_by
        link.deleted_at = now
        link.save(update_fields=["deleted_by", "deleted_at"])


document_link_repository = DocumentLinkRepository()
