from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.application.exceptions.exceptions import AppError
from app.application.services.document_service import DocumentService
from app.configuration.database_session_manager import DatabaseSessionManager
from app.configuration.dependencies import get_document_publisher, get_document_storage_service
from app.domain.dtos.document_response import DocumentResponseSchema
from app.infrastructure.messaging.publisher.interfaces.document_publisher_interface import DocumentPublisherInterface
from app.domain.dtos.document_request import DocumentRequest
from app.infrastructure.persistence.repositories.document_repository import DocumentRepository
from app.infrastructure.persistence.storages.interfaces.document_storage_service_interface import \
    DocumentStorageServiceInterface

logger = logging.getLogger(__name__)

db_session_manager = DatabaseSessionManager()

router = APIRouter()


class DocumentController:

    async def create_document(self,
                              request: DocumentRequest = Depends(DocumentRequest.as_form),
                              file: UploadFile = File(...),
                              document_publisher: DocumentPublisherInterface = Depends(get_document_publisher),
                              document_storage_service: DocumentStorageServiceInterface = Depends(get_document_storage_service),
                              db: Session = Depends(db_session_manager.get_db_session)) -> DocumentResponseSchema:
        try:
            service = DocumentService(
                document_repository=DocumentRepository(),
                document_publisher=document_publisher,
                document_storage_service=document_storage_service,
            )
            logger.info("Create document request received", extra={
                "uploaded_filename": getattr(file, "filename", None),
                "uploaded_content_type": getattr(file, "content_type", None)
            })
            document = await service.create_document(request, file, db)
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