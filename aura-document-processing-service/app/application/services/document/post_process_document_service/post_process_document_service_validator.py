from app.application.services.document.post_process_document_service.exceptions.post_process_document_service_exception import (
    PostProcessDocumentInvalidRequestException
)
from app.application.services.document.post_process_document_service.post_process_document_service_settings import (
    PostProcessDocumentServiceSettings
)
from app.domain.dtos.document.post_process_document.post_process_documents_request import (
    PostProcessDocumentsRequest
)


class PostProcessDocumentServiceValidator:
    def __init__(
            self,
            post_process_document_service_settings: PostProcessDocumentServiceSettings
    ) -> None:
        self._settings = post_process_document_service_settings

    def validate_documents_request(
            self,
            request: PostProcessDocumentsRequest
    ) -> None:
        self.validate_document_ids(request.document_ids)

    def validate_document_ids(
            self,
            document_ids: list[int]
    ) -> None:
        if not document_ids:
            raise PostProcessDocumentInvalidRequestException("At least one document identifier is required."
                                                             )
        if len(document_ids) > self._settings.max_document_ids:
            raise PostProcessDocumentInvalidRequestException(
                "The number of document identifiers exceeds the maximum allowed."
            )
        if any(doc_id <= 0 for doc_id in document_ids):
            raise PostProcessDocumentInvalidRequestException("Each document identifier must be a positive integer.")
        if len(document_ids) != len(set(document_ids)):
            raise PostProcessDocumentInvalidRequestException("Document identifiers must not contain duplicates.")
