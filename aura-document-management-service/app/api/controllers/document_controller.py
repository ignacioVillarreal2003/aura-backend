from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.application.exceptions.exceptions import AppError
from app.application.services.document_service import DocumentService
from app.configuration.database_session_manager import DatabaseSessionManager
from app.domain.dtos.document_response import DocumentResponseSchema
from app.infrastructure.messaging.publisher.rabbitmq_document_publisher import RabbitMQDocumentPublisher
from app.application.services.minio_storage_service import MinioStorageService
from app.domain.dtos.document_request import DocumentRequest
from app.infrastructure.persistence.repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)

db_session_manager = DatabaseSessionManager()

router = APIRouter()


class DocumentController:
    def __init__(self):
        self.service = DocumentService(
            document_repository=DocumentRepository(),
            document_publisher=RabbitMQDocumentPublisher(),
            storage_service=MinioStorageService(),
        )

    async def create_document(self,
                              request: DocumentRequest = Depends(DocumentRequest.as_form),
                              file: UploadFile = File(...),
                              db: Session = Depends(db_session_manager.get_db_session)) -> DocumentResponseSchema:
        try:
            logger.info("Create document request received", extra={
                "uploaded_filename": getattr(file, "filename", None),
                "uploaded_content_type": getattr(file, "content_type", None)
            })
            document = await self.service.create_document(request, file, db)
            logger.info("Create document succeeded", extra={"document_id": getattr(document, "id", None)})
            return document

        except AppError as e:
            logger.warning("Application error while creating document", extra={
                "error": e.code,
                "error_message": e.message
            })
            raise HTTPException(
                status_code=e.status_code,
                detail={"error": e.code, "message": e.message},
            )
        except Exception:
            logger.exception("Unexpected error while creating document")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "Unexpected error while uploading the document",
                },
            )


controller = DocumentController()
router.post("", response_model=DocumentResponseSchema)(controller.create_document)