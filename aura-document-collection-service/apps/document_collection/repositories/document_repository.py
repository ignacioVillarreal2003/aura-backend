from apps.document_collection.models import Document


class DocumentRepository:
    @staticmethod
    def exists_active_by_id(document_id: int) -> bool:
        return Document.objects.filter(pk=document_id, deleted_at__isnull=True).exists()

    @staticmethod
    def get_active_by_id(document_id: int) -> Document | None:
        return Document.objects.filter(pk=document_id, deleted_at__isnull=True).first()


document_repository = DocumentRepository()
