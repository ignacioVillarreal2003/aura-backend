import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.application.exceptions.app_exceptions import AppError
from app.application.services.document_summary_service import DocumentSummaryService
from app.configuration.dependencies import get_document_summary_service
from app.domain.dtos.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary_response import DocumentSummaryResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class DocumentSummaryController:
    async def execute_document_summary(self,
                                       request_body: DocumentSummaryRequest,
                                       document_summary_service: DocumentSummaryService = Depends(
                                           get_document_summary_service)) -> DocumentSummaryResponse:
        try:
            response = await document_summary_service.execute_document_summary(request_body)
            logger.info("Document summary request processed successfully")
            return response
        except AppError as e:
            logger.warning(f"App error in controller: {e.message}")
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": e.code,
                    "message": e.message
                }
            )
        except Exception:
            logger.exception("Unexpected error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred while generating the response",
                }
            )


controller = DocumentSummaryController()
router.post("", response_model=DocumentSummaryResponse)(controller.execute_document_summary)
