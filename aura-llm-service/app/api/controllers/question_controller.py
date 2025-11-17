from fastapi import APIRouter, Depends, HTTPException, status
import logging

from app.application.exceptions.api_exceptions import AppError
from app.application.services.question_service import QuestionService
from app.configuration.dependencies import get_question_service
from app.domain.dtos.question_request import QuestionRequest
from app.domain.dtos.question_response import QuestionResponse


logger = logging.getLogger(__name__)

router = APIRouter()


class QuestionController:
    async def generate_response(self,
                     request: QuestionRequest,
                                question_service: QuestionService = Depends(get_question_service)) -> QuestionResponse:
        try:
            return await question_service.generate_response(request)
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

controller = QuestionController()
router.post("", response_model=QuestionResponse)(controller.generate_response)