from app.application.services.document.post_process_document_service.exceptions.post_process_document_service_exception import (
    PostProcessDocumentInvalidRequestException,
)
from app.application.services.document.post_process_document_service.post_process_document_service_settings import (
    PostProcessDocumentServiceSettings,
)
from app.domain.dtos.document.post_process_document_controller.post_process_documents_request import (
    PostProcessDocumentsRequest,
)


class PostProcessDocumentServiceValidator:
    def __init__(self, post_process_document_service_settings: PostProcessDocumentServiceSettings) -> None:
        self._settings = post_process_document_service_settings

    def validate_documents_request(self, request: PostProcessDocumentsRequest) -> None:
        self.validate_document_ids(request.document_ids)

    def validate_document_ids(self, document_ids: list[int]) -> None:
        if not document_ids:
            raise PostProcessDocumentInvalidRequestException(
                "document_ids must not be empty"
            )
        if len(document_ids) > self._settings.max_document_ids:
            raise PostProcessDocumentInvalidRequestException(
                f"document_ids exceeds max size: {self._settings.max_document_ids}"
            )
        if any(doc_id <= 0 for doc_id in document_ids):
            raise PostProcessDocumentInvalidRequestException(
                "document_ids must contain only positive integers"
            )
        if len(document_ids) != len(set(document_ids)):
            raise PostProcessDocumentInvalidRequestException(
                "document_ids must not contain duplicates"
            )
