from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.application.services import document_service
from app.configuration.db_session import get_db_session
from app.domain.schemas.document_request_schema import DocumentRequestSchema
from app.domain.schemas.document_response_schema import DocumentResponseSchema
from app.application.exceptions.exceptions import AppError
import logging


router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=DocumentResponseSchema)
async def create_document(request: DocumentRequestSchema = Depends(DocumentRequestSchema.as_form),
                          file: UploadFile = File(...),
                          db: Session = Depends(get_db_session)):
    try:
        logger.info("Create document request received", extra={
            "uploaded_filename": getattr(file, "filename", None),
            "uploaded_content_type": getattr(file, "content_type", None)
        })
        document = await document_service.create_document(request, file, db)
        logger.info("Create document succeeded", extra={"document_id": getattr(document, "id", None)})
        return document
    except AppError as e:
        logger.warning("Application error while creating document", extra={
            "error": e.code,
            "message": e.message
        })
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": e.code,
                "message": e.message,
            },
        )
    except Exception as e:
        logger.exception("Unexpected error while creating document")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalServerError",
                "message": "Unexpected error while uploading the document",
            },
        )