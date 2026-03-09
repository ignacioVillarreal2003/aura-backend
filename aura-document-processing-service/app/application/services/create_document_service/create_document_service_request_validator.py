import logging
from typing import Optional
from fastapi import UploadFile

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentSizeExceededException,
    CreateDocumentInvalidException,
    CreateDocumentUnsupportedTypeException
)
from app.application.services.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings
)
from app.domain.dtos.create_document.create_document_request import CreateDocumentRequest

logger = logging.getLogger(__name__)


class CreateDocumentServiceRequestValidator:
    def __init__(
            self,
            create_document_service_settings: CreateDocumentServiceSettings
    ) -> None:
        self._create_document_service_settings = create_document_service_settings

    async def validate_create_document_request(
            self,
            raw_document: UploadFile,
            create_document_request: CreateDocumentRequest
    ) -> None:
        logger.debug(
            "Starting request validation",
            extra={
                "document_filename": raw_document.filename,
                "content_type": raw_document.content_type
            }
        )

        self._validate_document_file(raw_document)
        self._validate_type(raw_document)
        self._validate_size(raw_document)
        self._validate_filename(raw_document)
        await self._validate_magic_numbers(raw_document)

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
                    "document_filename": file.filename
                }
            )
            raise CreateDocumentInvalidException("File content type not provided")

        if not self._create_document_service_settings.is_content_type_allowed(content_type):
            logger.warning(
                "Unsupported content type",
                extra={
                    "content_type": content_type,
                    "document_filename": file.filename,
                    "allowed_types": self._create_document_service_settings.allowed_content_types
                }
            )
            raise CreateDocumentUnsupportedTypeException(
                f"File type '{content_type}' is not supported. "
                f"Allowed types: {', '.join(self._create_document_service_settings.allowed_content_types)}"
            )

        doc_type = self._create_document_service_settings.get_document_type(content_type)
        if not doc_type:
            logger.warning(
                "Content type not in mapping",
                extra={
                    "content_type": content_type
                }
            )
            raise CreateDocumentUnsupportedTypeException(f"Content type '{content_type}' is not mapped to a document type")

    def _validate_size(
            self,
            file: UploadFile
    ) -> None:
        max_bytes = self._create_document_service_settings.max_file_size_bytes
        min_bytes = self._create_document_service_settings.min_file_size_bytes

        file_size = self._get_file_size(file)

        if file_size is None:
            logger.warning(
                "Could not determine file size",
                extra={
                    "document_filename": file.filename
                }
            )
            raise CreateDocumentInvalidException("Could not determine file size")

        logger.debug(
            "Validating file size",
            extra={
                "document_filename": file.filename,
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
            raise CreateDocumentInvalidException(f"File too small. Minimum size: {min_bytes} bytes")

        if file_size > max_bytes:
            size_mb = file_size / (1024 * 1024)
            max_mb = self._create_document_service_settings.max_file_size_mb
            logger.warning(
                "File too large",
                extra={
                    "size_mb": round(size_mb, 2),
                    "max_mb": max_mb
                }
            )
            raise CreateDocumentSizeExceededException(
                f"File too large ({round(size_mb, 2)} MB). Maximum allowed: {max_mb} MB"
            )

    def _validate_filename(
            self,
            file: UploadFile
    ) -> None:
        filename = file.filename

        if ".." in filename or "/" in filename or "\\" in filename:
            logger.warning(
                "Potential path traversal in filename",
                extra={
                    "document_filename": filename
                }
            )
            raise CreateDocumentInvalidException("Filename contains invalid characters (path separators)")

        if "\x00" in filename:
            logger.warning(
                "Null byte in filename",
                extra={
                    "document_filename": filename
                }
            )
            raise CreateDocumentInvalidException("Filename contains null bytes")

        if len(filename) > 255:
            logger.warning(
                "Filename too long",
                extra={
                    "length": len(filename)
                }
            )
            raise CreateDocumentInvalidException("Filename too long (max 255 characters)")

    async def _validate_magic_numbers(
            self,
            file: UploadFile
    ) -> None:
        content_type = file.content_type
        magic_numbers = self._create_document_service_settings.get_magic_numbers(content_type)

        if not magic_numbers:
            logger.debug(
                "No magic numbers configured for content type",
                extra={
                    "content_type": content_type
                }
            )
            return

        try:
            await file.seek(0)
            header = await file.read(8)
            await file.seek(0)

            if not header:
                raise CreateDocumentInvalidException("Cannot read file header")

            is_valid = any(header.startswith(magic) for magic in magic_numbers)

            if not is_valid:
                logger.warning(
                    "Magic number validation failed",
                    extra={
                        "document_filename": file.filename,
                        "content_type": content_type,
                        "header": header[:8].hex()
                    }
                )
                raise CreateDocumentInvalidException(
                    f"File content does not match declared type '{content_type}'. "
                    f"Possible file type spoofing."
                )

            logger.debug(
                "Magic number validation passed",
                extra={
                    "document_filename": file.filename,
                    "content_type": content_type
                }
            )

        except CreateDocumentInvalidException:
            raise

        except Exception as e:
            logger.error(
                "Failed to validate magic numbers",
                extra={
                    "document_filename": file.filename,
                    "error": str(e)
                }
            )
            raise CreateDocumentInvalidException(f"Failed to validate file content: {e}")

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
                "Could not determine file size",
                extra={
                    "document_filename": file.filename,
                    "error": str(e)
                }
            )
            return None
