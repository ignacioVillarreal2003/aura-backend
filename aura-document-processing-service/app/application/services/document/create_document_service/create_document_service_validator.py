import logging
from typing import Optional
from fastapi import UploadFile

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings
)
from app.application.services.document.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentInvalidException,
    CreateDocumentSizeExceededException,
    CreateDocumentUnsupportedTypeException
)
from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest

logger = logging.getLogger(__name__)


class CreateDocumentServiceValidator:
    def __init__(
            self,
            create_document_service_settings: CreateDocumentServiceSettings
    ) -> None:
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
    def validate_chat_id(
            chat_id: int
    ) -> None:
        if chat_id <= 0:
            raise CreateDocumentInvalidException("The chat identifier must be a positive number.")

    @staticmethod
    def _validate_file_present(
            file: UploadFile
    ) -> None:
        if file is None:
            raise RequestValidationException("No file was provided.", status_code=400)
        if not file.filename:
            raise RequestValidationException("The file must have a filename.", status_code=400)

    @staticmethod
    def _validate_filename(
            file: UploadFile
    ) -> None:
        filename = file.filename
        if ".." in filename or "/" in filename or "\\" in filename:
            raise CreateDocumentInvalidException(
                "The filename contains invalid characters. Path separators are not allowed."
            )
        if "\x00" in filename:
            raise CreateDocumentInvalidException("The filename contains null bytes.")
        if len(filename) > 255:
            raise CreateDocumentInvalidException("The filename is too long. The maximum length is 255 characters.")

    def _validate_content_type(
            self,
            file: UploadFile
    ) -> None:
        content_type = file.content_type
        if not content_type:
            raise CreateDocumentInvalidException("The file content type was not provided.")
        if not self._settings.is_content_type_allowed(content_type):
            raise CreateDocumentUnsupportedTypeException(
                "This file type is not supported. Please upload a supported document format."
            )

    def _validate_size(
            self,
            file: UploadFile
    ) -> None:
        file_size = self._get_file_size(file)
        if file_size is None:
            raise CreateDocumentInvalidException("The file size could not be determined.")

        min_bytes = self._settings.min_file_size_bytes
        max_bytes = self._settings.max_file_size_bytes
        if file_size < min_bytes:
            raise CreateDocumentInvalidException("The file is smaller than the minimum allowed size.")
        if file_size > max_bytes:
            raise CreateDocumentSizeExceededException("The file is larger than the maximum allowed size.")

    async def _validate_magic_numbers(
            self,
            file: UploadFile
    ) -> None:
        content_type = file.content_type
        magic_numbers = self._settings.get_magic_numbers(content_type)
        if not magic_numbers:
            return
        try:
            await file.seek(0)
            header = await file.read(8)
            await file.seek(0)
            if not header:
                raise CreateDocumentInvalidException("The file header could not be read.")
            if not any(header.startswith(magic) for magic in magic_numbers):
                raise CreateDocumentInvalidException(
                    "The file content does not match the declared type. The file may be invalid or mislabeled."
                )
        except CreateDocumentInvalidException:
            raise
        except Exception as e:
            raise CreateDocumentInvalidException("Failed to validate the file content.") from e

    @staticmethod
    def _get_file_size(
            file: UploadFile
    ) -> Optional[int]:
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
