from apps.document_collection_documents.models import Document


class DocumentRepository:
    def exists_active_by_id(self, document_id: int) -> bool:
        return Document.objects.filter(pk=document_id, deleted_at__isnull=True).exists()

    def get_active_by_id(self, document_id: int) -> Document | None:
        return Document.objects.filter(pk=document_id, deleted_at__isnull=True).first()


document_repository = DocumentRepository()
