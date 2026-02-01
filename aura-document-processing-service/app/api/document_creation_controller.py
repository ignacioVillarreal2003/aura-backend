from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
import logging

from app.api.interfaces.document_creation_controller_interface import DocumentCreationControllerInterface
from app.application.exceptions.app_exception import AppError
from app.application.services.document_creation_service.interfaces.document_creation_service_interface import (
    DocumentCreationServiceInterface
)
from app.configuration.dependencies import get_database_session, get_document_creation_service
from app.domain.dtos.document_creation_request import DocumentCreationRequest
from app.domain.dtos.document_creation_response import DocumentCreationResponse

logger = logging.getLogger(__name__)


class DocumentCreationController(DocumentCreationControllerInterface):
    async def execute_document_creation(
            self,
            background_tasks: BackgroundTasks,
            document_creation_request: DocumentCreationRequest,
            raw_document: UploadFile = File(...),
            document_creation_service: DocumentCreationServiceInterface = Depends(get_document_creation_service),
            db: Session = Depends(get_database_session)
    ) -> DocumentCreationResponse:
        logger.info("Processing document creation request")

        try:
            document_creation_response = await document_creation_service.execute_document_creation(
                document_creation_request=document_creation_request,
                raw_document=raw_document,
                background_tasks=background_tasks,
                db=db
            )

            logger.info("Document creation request processed successfully")

            return document_creation_response

        except AppError as e:
            logger.warning(
                "Application error occurred while processing the document creation request",
                extra={
                    "error_code": e.code,
                    "error_message": e.message,
                    "status_code": e.status_code
                }
            )
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": e.code,
                    "message": e.message
                }
            )

        except Exception as e:
            logger.exception(
                "Unexpected error occurred while processing the document creation request",
                extra={
                    "error_type": type(e).__name__
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred while processing the document creation request"
                }
            )


router = APIRouter()

document_context_controller = DocumentCreationController()

router.post(
    "",
    response_model=DocumentCreationResponse
)(document_context_controller.execute_document_creation)
