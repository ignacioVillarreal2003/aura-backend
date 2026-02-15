import logging
from typing import Dict, Optional
from fastapi import UploadFile

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document_creation_service.document_creation_service_settings import (
    DocumentCreationServiceSettings
)
from app.application.services.document_creation_service.exceptions.document_creation_service_exception import (
    UnsupportedDocumentTypeError,
    DocumentSizeExceededError,
    InvalidDocumentError
)
from app.domain.constants.document_type import DocumentType
from app.domain.dtos.document_creation.document_creation_request import DocumentCreationRequest

logger = logging.getLogger(__name__)


class DocumentCreationServiceRequestValidator:
    _CONTENT_TYPE_MAPPING: Dict[str, DocumentType] = {
        "application/pdf": DocumentType.pdf,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocumentType.docx
    }

    def __init__(
            self,
            document_creation_service_settings: DocumentCreationServiceSettings
    ) -> None:
        self._document_creation_service_settings = document_creation_service_settings

    def validate_request(
            self,
            document_creation_request: DocumentCreationRequest,
            raw_document: UploadFile
    ) -> None:
        logger.debug(
            "Starting request validation",
            extra={
                "filename": raw_document.filename,
                "content_type": raw_document.content_type
            }
        )

        self._validate_document_file(raw_document)

        self._validate_type(raw_document)

        self._validate_size(raw_document)

        if self._document_creation_service_settings.strict_validation:
            self._validate_filename(raw_document)

        logger.debug("Request validation completed successfully")

    def _validate_document_file(
            self,
            file: UploadFile
    ) -> None:
        if file is None:
            logger.warning("No file provided in request")
            raise RequestValidationException(
                "No file provided",
                status_code=400
            )

        if not file.filename:
            logger.warning("File has no filename")
            raise RequestValidationException(
                "File must have a filename",
                status_code=400
            )

    def _validate_type(
            self,
            file: UploadFile
    ) -> None:
        content_type = file.content_type

        if not content_type:
            logger.warning(
                "No content type provided",
                extra={
                    "filename": file.filename
                }
            )
            raise InvalidDocumentError("File content type not provided")

        if not self._document_creation_service_settings.is_content_type_allowed(content_type):
            logger.warning(
                "Unsupported content type",
                extra={
                    "content_type": content_type,
                    "filename": file.filename,
                    "allowed_types": self._document_creation_service_settings.allowed_content_types
                }
            )
            raise UnsupportedDocumentTypeError(
                f"File type '{content_type}' is not supported. "
                f"Allowed types: {', '.join(self._document_creation_service_settings.allowed_content_types)}"
            )

        if content_type not in self._CONTENT_TYPE_MAPPING:
            logger.warning(
                "Content type not in mapping",
                extra={
                    "content_type": content_type
                }
            )
            raise UnsupportedDocumentTypeError(f"Content type '{content_type}' is not mapped to a document type")

    def _validate_size(
            self,
            file: UploadFile
    ) -> None:
        max_bytes = self._document_creation_service_settings.max_file_size_bytes
        min_bytes = self._document_creation_service_settings.min_file_size_bytes

        file_size = self._get_file_size(file)

        if file_size is None:
            logger.warning(
                "Could not determine file size",
                extra={
                    "filename": file.filename
                }
            )
            if self._document_creation_service_settings.strict_validation:
                raise InvalidDocumentError("Could not determine file size")
            return

        logger.debug(
            "Validating file size",
            extra={
                "filename": file.filename,
                "size_bytes": file_size,
                "max_bytes": max_bytes,
                "min_bytes": min_bytes
            }
        )

        if file_size < min_bytes:
            logger.warning(
                "File too small",
                extra={
                    "size": file_size,
                    "min": min_bytes
                }
            )
            raise InvalidDocumentError(f"File too small. Minimum size: {min_bytes} bytes")

        if file_size > max_bytes:
            size_mb = file_size / (1024 * 1024)
            max_mb = self._document_creation_service_settings.max_file_size_mb

            logger.warning(
                "File too large",
                extra={
                    "size_mb": round(size_mb, 2),
                    "max_mb": max_mb
                }
            )
            raise DocumentSizeExceededError(f"File too large ({round(size_mb, 2)} MB). Maximum allowed: {max_mb} MB")

    def _validate_filename(
            self,
            file: UploadFile
    ) -> None:
        filename = file.filename

        if '..' in filename or '/' in filename or '\\' in filename:
            logger.warning(
                "Potential path traversal in filename",
                extra={
                    "filename": filename
                }
            )
            raise InvalidDocumentError("Filename contains invalid characters (path separators)")

        if '\x00' in filename:
            logger.warning(
                "Null byte in filename",
                extra={
                    "filename": filename
                }
            )
            raise InvalidDocumentError("Filename contains null bytes")

        if len(filename) > 255:
            logger.warning(
                "Filename too long",
                extra={
                    "length": len(filename)
                }
            )
            raise InvalidDocumentError("Filename too long (max 255 characters)")

    def _get_file_size(
            self,
            file: UploadFile
    ) -> Optional[int]:
        file_size = getattr(file, "size", None)

        if file_size is not None:
            return file_size

        try:
            current_pos = file.file.tell()
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(current_pos)
            return file_size
        except Exception as e:
            logger.debug(
                f"Could not determine file size: {e}",
                extra={
                    "filename": file.filename
                }
            )
            return None

    def get_raw_document_type(
            self,
            raw_document: UploadFile
    ) -> DocumentType:
        logger.debug(
            "Getting document type",
            extra={
                "filename": raw_document.filename,
                "content_type": raw_document.content_type
            }
        )

        content_type = raw_document.content_type

        if content_type not in self._CONTENT_TYPE_MAPPING:
            raise UnsupportedDocumentTypeError(f"Content type '{content_type}' is not supported")

        document_type = self._CONTENT_TYPE_MAPPING[content_type]

        logger.debug(
            "Document type determined",
            extra={
                "document_type": document_type.value
            }
        )

        return document_type
