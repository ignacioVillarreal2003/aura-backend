from fastapi import APIRouter, Depends, HTTPException, status
import logging

from app.application.services.summary_service import SummaryService
from app.domain.dtos.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary_response import DocumentSummaryResponse
from app.configuration.dependencies import get_summary_service
from app.application.exceptions.app_exceptions import AppError

logger = logging.getLogger(__name__)
router = APIRouter()


class DocumentSummaryController:
    async def execute_document_summary(self,
                                       request: DocumentSummaryRequest,
                                       document_summary_service: SummaryService = Depends(
                                           get_summary_service)) -> DocumentSummaryResponse:
        try:
            return await document_summary_service.summarize(request)
        except AppError as e:
            logger.warning("Application error while generating response")
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": e.code,
                    "message": e.message
                },
            )
        except Exception:
            logger.exception("Unexpected error while generating response")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "Ha ocurrido un error inesperado al generar la respuesta",
                }
            )


controller = DocumentSummaryController()
router.post("", response_model=DocumentSummaryResponse)(controller.execute_document_summary)
