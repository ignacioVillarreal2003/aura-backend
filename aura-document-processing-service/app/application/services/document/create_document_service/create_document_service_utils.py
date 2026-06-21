import logging
from fastapi import UploadFile

from app.application.services.document.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings,
)
from app.application.services.document.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentUnsupportedTypeException,
)
from app.domain.constants.document.document_mime_type import DocumentMimeType

logger = logging.getLogger(__name__)


class CreateDocumentServiceUtils:
    def __init__(
            self,
            create_document_service_settings: CreateDocumentServiceSettings
    ) -> None:
        self._settings = create_document_service_settings

    def get_document_mime_type(
            self,
            raw_document: UploadFile
    ) -> DocumentMimeType:
        content_type = raw_document.content_type
        if not content_type:
            raise CreateDocumentUnsupportedTypeException("This content type is not supported.")

        doc_type_str = self._settings.get_document_type(content_type)

        if not doc_type_str:
            raise CreateDocumentUnsupportedTypeException("This content type is not supported.")

        try:
            mime_type = DocumentMimeType(doc_type_str)
        except ValueError:
            raise CreateDocumentUnsupportedTypeException(
                "This content type could not be mapped to a supported document format."
            ) from None

        logger.debug(
            "The document MIME type was resolved.",
            extra={
                "document_filename": raw_document.filename,
                "mime_type": mime_type.value
            }
        )
        return mime_type
