from typing import Dict
import logging

from app.application.services import minio_service
from app.configuration.environment_variables import environment_variables
from app.domain.constants.document_type import DocumentType
from app.application.exceptions.exceptions import UnsupportedFileTypeError, ValidationError, StorageError, DatabaseError
from app.domain.models.document import Document
from app.domain.schemas.document_request_schema import DocumentRequestSchema
from app.domain.schemas.document_response_schema import DocumentResponseSchema
from app.persistence.repositories.document_repository import DocumentRepository


logger = logging.getLogger(__name__)


async def create_document(request: DocumentRequestSchema, file, db) -> DocumentResponseSchema:
    content_type_to_doc_type: Dict[str, DocumentType] = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocumentType.docx,
        "application/pdf": DocumentType.pdf,
    }

    if file is None:
        logger.warning("No file provided in request")
        raise ValidationError("No file provided")

    if file.content_type not in content_type_to_doc_type:
        logger.warning("Unsupported content type", extra={"content_type": file.content_type})
        raise UnsupportedFileTypeError("Only PDF and DOCX files are supported")

    max_bytes = environment_variables.max_file_size_mb * 1024 * 1024
    if hasattr(file, "size") and file.size is not None and file.size > max_bytes:
        logger.warning("File exceeds max size", extra={
            "size": getattr(file, "size", None),
            "max_bytes": max_bytes
        })
        raise ValidationError(f"File exceeds maximum size of {environment_variables.max_file_size_mb} MB")

    try:
        logger.info("Uploading file to storage")
        path = await minio_service.upload_document(file)
        logger.info("File uploaded to storage", extra={"path": path})
    except StorageError:
        raise

    document = Document(
        title=file.filename,
        type=content_type_to_doc_type[file.content_type],
        path=path,
        size=getattr(file, "size", None),
        created_by=1,
    )

    try:
        logger.info("Persisting document to database")
        db_document = DocumentRepository.create(db, document)
        logger.info("Document persisted", extra={"document_id": db_document.id})
    except DatabaseError:
        raise

    return DocumentResponseSchema(
        id=db_document.id,
        title=db_document.title,
        status=db_document.status
    )