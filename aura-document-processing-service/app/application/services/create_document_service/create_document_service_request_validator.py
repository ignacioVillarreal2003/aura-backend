import logging
from typing import Optional
from fastapi import UploadFile

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings
)
from app.application.services.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentInvalidException,
    CreateDocumentSizeExceededException,
    CreateDocumentUnsupportedTypeException
)
from app.domain.dtos.create_document.create_document_request import CreateDocumentRequest

logger = logging.getLogger(__name__)


class CreateDocumentServiceRequestValidator:
    def __init__(self, create_document_service_settings: CreateDocumentServiceSettings) -> None:
        self._settings = create_document_service_settings

    async def validate_create_document_request(
            self,
            raw_document: UploadFile,
            create_document_request: CreateDocumentRequest
    ) -> None:
        logger.debug(
            "Starting request validation",
            extra={
                "document_filename": raw_document.filename,
                "content_type": raw_document.content_type,
            },
        )

        self._validate_file_present(raw_document)
        self._validate_filename(raw_document)
        self._validate_content_type(raw_document)
        self._validate_size(raw_document)
        await self._validate_magic_numbers(raw_document)

        logger.debug("Request validation completed successfully")

    def _validate_file_present(self, file: UploadFile) -> None:
        if file is None:
            raise RequestValidationException("No file provided", status_code=400)
        if not file.filename:
            raise RequestValidationException("File must have a filename", status_code=400)

    def _validate_filename(self, file: UploadFile) -> None:
        filename = file.filename

        if ".." in filename or "/" in filename or "\\" in filename:
            logger.warning("Potential path traversal in filename", extra={"filename": filename})
            raise CreateDocumentInvalidException(
                "Filename contains invalid characters (path separators not allowed)"
            )

        if "\x00" in filename:
            logger.warning("Null byte in filename", extra={"filename": filename})
            raise CreateDocumentInvalidException("Filename contains null bytes")

        if len(filename) > 255:
            logger.warning("Filename too long", extra={"length": len(filename)})
            raise CreateDocumentInvalidException("Filename too long (max 255 characters)")

    def _validate_content_type(self, file: UploadFile) -> None:
        content_type = file.content_type

        if not content_type:
            raise CreateDocumentInvalidException("File content type not provided")

        if not self._settings.is_content_type_allowed(content_type):
            logger.warning(
                "Unsupported content type",
                extra={
                    "content_type": content_type,
                    "document_filename": file.filename,
                    "allowed": self._settings.allowed_content_types
                }
            )
            raise CreateDocumentUnsupportedTypeException(
                f"File type '{content_type}' is not supported. "
                f"Allowed types: {', '.join(self._settings.allowed_content_types)}"
            )

    def _validate_size(self, file: UploadFile) -> None:
        file_size = self._get_file_size(file)

        if file_size is None:
            logger.warning("Could not determine file size", extra={"document_filename": file.filename})
            raise CreateDocumentInvalidException("Could not determine file size")

        min_bytes = self._settings.min_file_size_bytes
        max_bytes = self._settings.max_file_size_bytes

        logger.debug(
            "Validating file size",
            extra={"document_filename": file.filename, "size_bytes": file_size, "min": min_bytes, "max": max_bytes}
        )

        if file_size < min_bytes:
            raise CreateDocumentInvalidException(
                f"File too small ({file_size} bytes). Minimum: {min_bytes} bytes"
            )

        if file_size > max_bytes:
            size_mb = round(file_size / (1024 * 1024), 2)
            raise CreateDocumentSizeExceededException(
                f"File too large ({size_mb} MB). Maximum: {self._settings.max_file_size_mb} MB"
            )

    async def _validate_magic_numbers(self, file: UploadFile) -> None:
        content_type = file.content_type
        magic_numbers = self._settings.get_magic_numbers(content_type)

        if not magic_numbers:
            logger.debug(
                "No magic numbers configured for content type",
                extra={"content_type": content_type}
            )
            return

        try:
            await file.seek(0)
            header = await file.read(8)
            await file.seek(0)

            if not header:
                raise CreateDocumentInvalidException("Cannot read file header")

            if not any(header.startswith(magic) for magic in magic_numbers):
                logger.warning(
                    "Magic number validation failed",
                    extra={
                        "document_filename": file.filename,
                        "content_type": content_type,
                        "header_hex": header.hex()
                    }
                )
                raise CreateDocumentInvalidException(
                    f"File content does not match declared type '{content_type}'. "
                    "Possible file type spoofing."
                )

            logger.debug(
                "Magic number validation passed",
                extra={"document_filename": file.filename, "content_type": content_type}
            )

        except CreateDocumentInvalidException:
            raise
        except Exception as e:
            logger.error(
                "Failed to validate magic numbers",
                extra={"document_filename": file.filename, "error": str(e)}
            )
            raise CreateDocumentInvalidException(f"Failed to validate file content: {e}") from e

    def _get_file_size(self, file: UploadFile) -> Optional[int]:
        file_size = getattr(file, "size", None)
        if file_size is not None:
            return file_size

        try:
            current_pos = file.file.tell()
            file.file.seek(0, 2)
            size = file.file.tell()
            file.file.seek(current_pos)
            return size
        except Exception as e:
            logger.debug(
                "Could not determine file size via seek",
                extra={"document_filename": file.filename, "error": str(e)}
            )
            return None
