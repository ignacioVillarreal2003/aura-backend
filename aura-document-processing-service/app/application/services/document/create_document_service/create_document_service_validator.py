import logging
from typing import Optional
from fastapi import UploadFile

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings,
)
from app.application.services.document.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentInvalidException,
    CreateDocumentSizeExceededException,
    CreateDocumentUnsupportedTypeException,
)
from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest

logger = logging.getLogger(__name__)


class CreateDocumentServiceValidator:
    def __init__(self, create_document_service_settings: CreateDocumentServiceSettings) -> None:
        self._settings = create_document_service_settings

    async def validate_create_document_request(
            self,
            raw_document: UploadFile,
            create_document_request: CreateDocumentRequest
    ) -> None:
        self.validate_chat_id(create_document_request.chat_id)
        self._validate_file_present(raw_document)
        self._validate_filename(raw_document)
        self._validate_content_type(raw_document)
        self._validate_size(raw_document)
        await self._validate_magic_numbers(raw_document)

    @staticmethod
    def validate_chat_id(chat_id: int) -> None:
        if chat_id <= 0:
            raise CreateDocumentInvalidException(
                f"chat_id must be a positive integer, got {chat_id}"
            )

    def _validate_file_present(self, file: UploadFile) -> None:
        if file is None:
            raise RequestValidationException("No file provided", status_code=400)
        if not file.filename:
            raise RequestValidationException("File must have a filename", status_code=400)

    def _validate_filename(self, file: UploadFile) -> None:
        filename = file.filename
        if ".." in filename or "/" in filename or "\\" in filename:
            raise CreateDocumentInvalidException(
                "Filename contains invalid characters (path separators not allowed)"
            )
        if "\x00" in filename:
            raise CreateDocumentInvalidException("Filename contains null bytes")
        if len(filename) > 255:
            raise CreateDocumentInvalidException("Filename too long (max 255 characters)")

    def _validate_content_type(self, file: UploadFile) -> None:
        content_type = file.content_type
        if not content_type:
            raise CreateDocumentInvalidException("File content type not provided")
        if not self._settings.is_content_type_allowed(content_type):
            raise CreateDocumentUnsupportedTypeException(
                f"File type '{content_type}' is not supported. "
                f"Allowed types: {', '.join(self._settings.allowed_content_types)}"
            )

    def _validate_size(self, file: UploadFile) -> None:
        file_size = self._get_file_size(file)
        if file_size is None:
            raise CreateDocumentInvalidException("Could not determine file size")

        min_bytes = self._settings.min_file_size_bytes
        max_bytes = self._settings.max_file_size_bytes
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
            return
        try:
            await file.seek(0)
            header = await file.read(8)
            await file.seek(0)
            if not header:
                raise CreateDocumentInvalidException("Cannot read file header")
            if not any(header.startswith(magic) for magic in magic_numbers):
                raise CreateDocumentInvalidException(
                    f"File content does not match declared type '{content_type}'. "
                    "Possible file type spoofing."
                )
        except CreateDocumentInvalidException:
            raise
        except Exception as e:
            raise CreateDocumentInvalidException(f"Failed to validate file content: {e}") from e

    @staticmethod
    def _get_file_size(file: UploadFile) -> Optional[int]:
        file_size = getattr(file, "size", None)
        if file_size is not None:
            return file_size
        try:
            current_pos = file.file.tell()
            file.file.seek(0, 2)
            size = file.file.tell()
            file.file.seek(current_pos)
            return size
        except Exception:
            return None
