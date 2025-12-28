from app.application.exceptions.app_exceptions import ValidationError
from app.application.services.document_summary_service.document_summary_configuration import DocumentSummaryConfiguration
from app.domain.dtos.document_summary_request import DocumentSummaryRequest


class DocumentSummaryRequestValidator:
    def __init__(self,
                 configuration: DocumentSummaryConfiguration):
        self._configuration = configuration

    def validate_request(self,
                         request: DocumentSummaryRequest) -> None:
        self._validate_document_id(request.document_id)

    def _validate_document_id(self,
                              document_id: int) -> None:
        if document_id < self._configuration.MIN_DOCUMENT_ID:
            raise ValidationError(
                f"Document ID must be at least {self._configuration.MIN_DOCUMENT_ID}",
                status_code=400
            )