import logging

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document_summary_service.document_summary_settings import DocumentSummaryServiceSettings
from app.domain.dtos.document_summary.document_summary_request import DocumentSummaryRequest

logger = logging.getLogger(__name__)


class DocumentSummaryRequestValidator:
    _MIN_DOCUMENT_ID: int = 1
    _MAX_DOCUMENT_ID: int = 2_147_483_647

    def __init__(self, document_summary_service_settings: DocumentSummaryServiceSettings) -> None:
        self._settings = document_summary_service_settings

    def validate_request(self, request: DocumentSummaryRequest) -> None:
        logger.debug("Starting request validation")
        self._validate_document_id(document_id=request.document_id)
        logger.debug("Request validation completed successfully")

    def _validate_document_id(self, document_id: int) -> None:
        if not (self._MIN_DOCUMENT_ID <= document_id <= self._MAX_DOCUMENT_ID):
            logger.warning(
                "Document ID validation failed: value out of allowed range",
                extra={
                    "document_id": document_id,
                    "min": self._MIN_DOCUMENT_ID,
                    "max": self._MAX_DOCUMENT_ID
                }
            )
            raise RequestValidationException(
                f"El identificador del documento es inválido. "
                f"Debe estar entre {self._MIN_DOCUMENT_ID} y {self._MAX_DOCUMENT_ID}. "
                f"Valor recibido: {document_id}.",
                status_code=400
            )
