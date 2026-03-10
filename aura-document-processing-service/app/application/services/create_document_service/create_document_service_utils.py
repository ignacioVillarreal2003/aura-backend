import hashlib
import logging
from fastapi import UploadFile

from app.application.services.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings
)
from app.application.services.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentUnsupportedTypeException
)
from app.domain.constants.document_mime_type import DocumentMimeType

logger = logging.getLogger(__name__)


class CreateDocumentServiceUtils:
    def __init__(
            self,
            create_document_service_settings: CreateDocumentServiceSettings
    ) -> None:
        self._create_document_service_settings = create_document_service_settings

    def get_document_mime_type(
            self,
            raw_document: UploadFile
    ) -> DocumentMimeType:
        logger.debug(
            "Getting document mime type",
            extra={
                "document_filename": raw_document.filename,
                "content_type": raw_document.content_type
            }
        )

        content_type = raw_document.content_type
        doc_type_str = self._create_document_service_settings.get_document_type(content_type)

        if not doc_type_str:
            raise CreateDocumentUnsupportedTypeException(f"Content type '{content_type}' is not supported")

        try:
            document_mime_type = DocumentMimeType(doc_type_str)
        except ValueError:
            raise CreateDocumentUnsupportedTypeException(f"Invalid document type: '{doc_type_str}'")

        logger.debug(
            "Document mime type determined",
            extra={
                "document_mime_type": document_mime_type.value
            }
        )

        return document_mime_type

    async def compute_file_hash(
            self,
            file: UploadFile
    ) -> str:
        try:
            hasher = hashlib.sha256()

            await file.seek(0)

            while chunk := await file.read(self._create_document_service_settings.chunk_size_bytes):
                hasher.update(chunk)

            await file.seek(0)

            file_hash = hasher.hexdigest()

            logger.debug(
                "File hash computed",
                extra={
                    "document_filename": file.filename,
                    "hash": file_hash[:16] + "..."
                }
            )

            return file_hash

        except Exception as e:
            logger.error(
                "Failed to compute file hash",
                extra={
                    "document_filename": file.filename,
                    "error": str(e)
                }
            )
            raise
