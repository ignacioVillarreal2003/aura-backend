from django.db.models import QuerySet

from apps.document_collection_documents.models import DocumentInDocumentCollection


class DocumentInDocumentCollectionRepository:
    def list_active_by_document_collection_id(
        self, document_collection_id: int
    ) -> QuerySet[DocumentInDocumentCollection]:
        return (
            DocumentInDocumentCollection.objects.filter(document_collection_id=document_collection_id)
            .select_related("document")
            .order_by()
        )

    def get_active_by_document_collection_id_and_document_id(
        self,
        document_collection_id: int,
        document_id: int,
    ) -> DocumentInDocumentCollection | None:
        return (
            DocumentInDocumentCollection.objects.filter(
                document_collection_id=document_collection_id,
                document_id=document_id,
            )
            .select_related("document")
            .first()
        )

    def get_active_by_id(self, document_in_document_collection_id: int) -> DocumentInDocumentCollection | None:
        return (
            DocumentInDocumentCollection.objects.filter(pk=document_in_document_collection_id)
            .select_related("document")
            .first()
        )

    def create(
        self,
        document_collection_id: int,
        document_id: int,
        created_by: int,
    ) -> DocumentInDocumentCollection:
        return DocumentInDocumentCollection.objects.create(
            document_collection_id=document_collection_id,
            document_id=document_id,
            created_by=created_by,
        )

    def soft_delete(self, document_in_document_collection: DocumentInDocumentCollection, deleted_by: int) -> None:
        document_in_document_collection.delete(deleted_by=deleted_by)


document_in_document_collection_repository = DocumentInDocumentCollectionRepository()
