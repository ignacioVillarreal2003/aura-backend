from fastapi import APIRouter, Depends, HTTPException, status
import logging

from app.api.controllers.interfaces.summary_controller_interface import SummaryControllerInterface
from app.application.services.summary_service import SummaryService
from app.domain.dtos.summary_request import SummaryRequest
from app.domain.dtos.summary_response import SummaryResponse
from app.configuration.dependencies import get_summary_service
from app.application.exceptions.api_exceptions import AppError

logger = logging.getLogger(__name__)
router = APIRouter()


class SummaryController(SummaryControllerInterface):
    async def summarize(self,
                        request: SummaryRequest,
                        summary_service: SummaryService = Depends(get_summary_service)) -> SummaryResponse:
        try:
            return await summary_service.summarize(request)
        except AppError as e:
            logger.warning("Error en summarization", extra={
                "error": e.code,
                "error_message": e.message
            })
            raise HTTPException(
                status_code=e.status_code,
                detail={"error": e.code, "message": e.message}
            )
        except Exception:
            logger.exception("Unexpected error while summarizing")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "Unexpected error while summarizing the document"
                },
            )


controller = SummaryController()
router.post("", response_model=SummaryResponse)(controller.summarize)
