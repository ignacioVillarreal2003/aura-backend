import logging
from typing import Dict
from fastapi import UploadFile

from app.application.exceptions.app_exception import ValidationError
from app.application.services.document_creation_service.document_creation_service_configuration import (
    DocumentCreationServiceConfiguration
)
from app.application.services.document_creation_service.exceptions.document_creation_service_exception import (
    UnsupportedDocumentTypeError
)
from app.domain.constants.document_type import DocumentType
from app.domain.dtos.document_creation.document_creation_request import DocumentCreationRequest

logger = logging.getLogger(__name__)


class DocumentCreationServiceRequestValidator:
    _CONTENT_TYPE_MAPPING: Dict[str, DocumentType] = {
        "application/pdf": DocumentType.PDF,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocumentType.DOCX,
    }

    def __init__(
            self,
            document_creation_service_configuration: DocumentCreationServiceConfiguration
    ) -> None:
        self._document_creation_service_configuration = document_creation_service_configuration
        logger.debug("DocumentCreationServiceRequestValidator initialized")

    def validate_request(
            self,
            document_creation_request: DocumentCreationRequest,
            raw_document: UploadFile
    ) -> None:
        logger.debug("Starting validation")

        self._validate_raw_document(raw_document)

        logger.debug("Validation completed successfully")

    def _validate_raw_document(
            self, raw_document: UploadFile
    ) -> None:
        self._validate_type(raw_document)
        self._validate_size(raw_document)

    def _validate_type(
            self,
            file: UploadFile
    ) -> DocumentType:
        if file is None:
            logger.warning("No file provided in request")
            raise ValidationError(
                "No se proporcionó ningún archivo",
                status_code=400
            )

        content_type = file.content_type

        if content_type not in self._CONTENT_TYPE_MAPPING:
            logger.warning(
                "Unsupported content type",
                extra={"content_type": content_type}
            )
            raise UnsupportedDocumentTypeError()

        return self._CONTENT_TYPE_MAPPING[content_type]

    def _validate_size(
            self,
            file: UploadFile
    ) -> None:
        max_bytes = self._document_creation_service_configuration.max_file_size_mb * 1024 * 1024

        file_size = getattr(file, "size", None)

        if file_size is None:
            try:
                current_pos = file.file.tell()
                file.file.seek(0, 2)
                file_size = file.file.tell()
                file.file.seek(current_pos)
            except Exception:
                file_size = None

        logger.debug("Validating file size")

        if file_size is not None and file_size > max_bytes:
            logger.warning("File exceeds maximum size")
            raise ValidationError(
                f"El archivo excede el tamaño máximo permitido ({self._document_creation_service_configuration.max_file_size_mb} MB)",
                status_code=400
            )

    def get_raw_document_type(
            self,
            raw_document: UploadFile
    ) -> DocumentType:
        logger.debug("Getting raw document type")

        return self._validate_type(raw_document)
