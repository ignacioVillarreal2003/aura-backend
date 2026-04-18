from apps.document_collections.models import Document


class DocumentReadRepository:
    def exists_active(self, document_id: int) -> bool:
        return Document.objects.filter(pk=document_id, deleted_at__isnull=True).exists()


document_read_repository = DocumentReadRepository()
