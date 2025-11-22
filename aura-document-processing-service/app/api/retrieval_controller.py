from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.api.interfaces.retrieval_controller_interface import RetrievalControllerInterface
from app.application.exceptions.api_exceptions import AppError
from app.application.services.retrival_service import RetrievalService
from app.configuration.dependencies import get_db_session, get_retrieval_service
from app.domain.dtos.question_request import QuestionRequest
from app.domain.dtos.question_response import QuestionResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class RetrievalController(RetrievalControllerInterface):
    async def search_context(self,
                             question_request: QuestionRequest,
                             retrieval_service: RetrievalService = Depends(get_retrieval_service),
                             db: Session = Depends(get_db_session)) -> QuestionResponse:
        try:
            return retrieval_service.process_question(question_request, db)

        except AppError as e:
            logger.warning("Application error while retrieving context", extra={
                "error": e.code,
                "error_message": e.message
            })
            raise HTTPException(
                status_code=e.status_code,
                detail={"error": e.code, "message": e.message},
            )
        except Exception:
            logger.exception("Unexpected error while retrieving context")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "Ha ocurrido un error inesperado al procesar la solicitud",
                },
            )


controller = RetrievalController()
router.post("", response_model=QuestionResponse)(controller.search_context)
