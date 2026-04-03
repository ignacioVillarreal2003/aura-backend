from app.application.services.document.delete_document_service.delete_document_service_settings import (
    DeleteDocumentServiceSettings,
)
from app.application.services.document.delete_document_service.exceptions.delete_document_service_exception import (
    DeleteDocumentInvalidRequestException,
)


class DeleteDocumentServiceValidator:
    def __init__(
            self,
            delete_document_service_settings: DeleteDocumentServiceSettings
    ) -> None:
        self._settings = delete_document_service_settings

    @staticmethod
    def validate_document_id(
            document_id: int
    ) -> None:
        if document_id <= 0:
            raise DeleteDocumentInvalidRequestException("The document identifier must be a positive number.")

    @staticmethod
    def validate_chat_id(
            chat_id: int
    ) -> None:
        if chat_id <= 0:
            raise DeleteDocumentInvalidRequestException("The chat identifier must be a positive number.")

    def validate_documents_count(
            self,
            document_count: int
    ) -> None:
        if document_count > self._settings.max_ids_per_operation:
            raise DeleteDocumentInvalidRequestException(
                "The number of documents exceeds the limit for a single operation."
            )
