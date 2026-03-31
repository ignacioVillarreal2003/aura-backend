from app.application.services.document.delete_document_service.delete_document_service_settings import (
    DeleteDocumentServiceSettings,
)
from app.application.services.document.delete_document_service.exceptions.delete_document_service_exception import (
    DeleteDocumentInvalidRequestException,
)


class DeleteDocumentServiceValidator:
    def __init__(self, delete_document_service_settings: DeleteDocumentServiceSettings) -> None:
        self._settings = delete_document_service_settings

    def validate_document_id(self, document_id: int) -> None:
        if document_id <= 0:
            raise DeleteDocumentInvalidRequestException(
                f"document_id must be a positive integer, got {document_id}"
            )

    def validate_chat_id(self, chat_id: int) -> None:
        if chat_id <= 0:
            raise DeleteDocumentInvalidRequestException(
                f"chat_id must be a positive integer, got {chat_id}"
            )

    def validate_documents_count(self, document_count: int) -> None:
        if document_count > self._settings.max_ids_per_operation:
            raise DeleteDocumentInvalidRequestException(
                f"documents count ({document_count}) exceeds limit "
                f"({self._settings.max_ids_per_operation}) for one operation"
            )
