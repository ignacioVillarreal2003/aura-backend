import logging

from app.application.exceptions.app_exceptions import ValidationError
from app.application.services.document_summary_service.document_summary_configuration import (
    DocumentSummaryConfiguration
)
from app.domain.dtos.document_summary_request import DocumentSummaryRequest

logger = logging.getLogger(__name__)


class DocumentSummaryRequestValidator:
    def __init__(self,
                 configuration: DocumentSummaryConfiguration):
        self._configuration = configuration
        logger.debug("DocumentSummaryRequestValidator initialized")

    def validate_request(self,
                         request: DocumentSummaryRequest) -> None:
        logger.debug(
            "Starting request validation",
            extra={
                "document_id": request.document_id
            }
        )
        self._validate_document_id(request.document_id)

    def _validate_document_id(self,
                              document_id: int) -> None:
        logger.debug(
            "Validating document_id",
            extra={
                "document_id": document_id,
                "min_document_id": self._configuration.min_document_id,
                "max_document_id": self._configuration.max_document_id
            }
        )

        if not (self._configuration.min_document_id
                <= document_id
                <= self._configuration.max_document_id):
            logger.warning(
                "Document ID validation failed: value out of allowed range",
                extra={
                    "document_id": document_id,
                    "min_document_id": self._configuration.min_document_id,
                    "max_document_id": self._configuration.max_document_id
                }
            )
            raise ValidationError(
                "El identificador del documento es inválido. "
                f"Debe estar entre {self._configuration.min_document_id} y {self._configuration.max_document_id}. "
                f"Valor recibido: {document_id}.",
                status_code=400)
