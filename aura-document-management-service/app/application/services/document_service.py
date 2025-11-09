import logging
from datetime import datetime
from typing import Dict
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.application.services.interfaces.document_service_interface import DocumentServiceInterface
from app.application.services.interfaces.storage_service_interface import StorageServiceInterface
from app.configuration.environment_variables import environment_variables
from app.domain.constants.document_type import DocumentType
from app.application.exceptions.exceptions import UnsupportedFileTypeError, ValidationError, StorageError, DatabaseError
from app.domain.dtos.document_request import DocumentRequest
from app.domain.models.document import Document
from app.domain.dtos.document_response import DocumentResponseSchema
from app.infrastructure.messaging.publisher.interfaces.document_publisher_interface import DocumentPublisherInterface
from app.infrastructure.persistence.repositories.interfaces.document_repository_interface import DocumentRepositoryInterface


logger = logging.getLogger(__name__)


class DocumentService(DocumentServiceInterface):
    def __init__(self,
                 document_repository: DocumentRepositoryInterface,
                 document_publisher: DocumentPublisherInterface,
                 storage_service: StorageServiceInterface):
        self.document_repository = document_repository
        self.document_publisher = document_publisher
        self.storage_service = storage_service

    async def create_document(self,
                              request: DocumentRequest,
                              file: UploadFile,
                              db: Session) -> DocumentResponseSchema:
        document_type = self._validate_type(file)
        self._validate_size(file)

        try:
            logger.info("Uploading file to storage")
            path = await self.storage_service.upload_document(file)
            logger.info("File uploaded to storage", extra={"path": path})
        except StorageError:
            raise

        document = Document(
            file_name=file.filename,
            type=document_type,
            path=path,
            created_by=1,
            created_at=datetime.now()
        )

        try:
            logger.info("Persisting document to database")
            db_document = self.document_repository.create(document, db)
            logger.info("Document persisted", extra={"document_id": db_document.id})
            self.document_publisher.publish_document(db_document.id)
        except DatabaseError:
            raise

        return DocumentResponseSchema(
            id=db_document.id,
            file_name=db_document.file_name,
            status=db_document.status
        )

    def _validate_type(self, file) -> DocumentType:
        mapping: Dict[str, DocumentType] = {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocumentType.docx,
            "application/pdf": DocumentType.pdf,
        }
        if file is None:
            logger.warning("No file provided in request")
            raise ValidationError("No file provided")
        if file.content_type not in mapping:
            logger.warning("Unsupported content type", extra={"content_type": file.content_type})
            raise UnsupportedFileTypeError("Only PDF and DOCX files are supported")
        return mapping[file.content_type]

    def _validate_size(self, file):
        max_bytes = environment_variables.max_file_size_mb * 1024 * 1024
        if hasattr(file, "size") and file.size and file.size > max_bytes:
            logger.warning("File exceeds max size", extra={
                "size": getattr(file, "size", None),
                "max_bytes": max_bytes
            })
            raise ValidationError(f"File exceeds max size ({environment_variables.max_file_size_mb} MB)")
