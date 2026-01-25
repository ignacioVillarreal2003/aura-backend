import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.application.exceptions.app_exceptions import AppError
from app.application.services.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface
)
from app.configuration.dependencies import get_document_summary_service
from app.domain.dtos.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary_response import DocumentSummaryResponse

logger = logging.getLogger(__name__)


class DocumentSummaryController:
    @staticmethod
    async def execute_document_summary(document_summary_request: DocumentSummaryRequest,
                                       document_summary_service: DocumentSummaryServiceInterface = Depends(
                                           get_document_summary_service)) -> DocumentSummaryResponse:
        logger.info("Processing document summary request")

        try:
            document_summary_response = await document_summary_service.execute_document_summary(document_summary_request)

            logger.info("Document summary request processed successfully")

            return document_summary_response

        except AppError as e:
            logger.warning(
                "Application error in document summary controller",
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
                "Unexpected error in document summary controller",
                extra={
                    "error_type": type(e).__name__
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred while processing the document summary request"
                }
            )


router = APIRouter()

document_summary_controller = DocumentSummaryController()

router.post(
    "",
    response_model=DocumentSummaryResponse
)(document_summary_controller.execute_document_summary)
