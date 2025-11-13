from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.application.exceptions.exceptions import AppError
from app.application.services.retrival_service import RetrievalService
from app.configuration.dependencies import get_db_session, get_retrieval_service
from app.domain.dtos.fragment_response import FragmentResponse
from app.domain.dtos.question_request import QuestionRequest
from app.domain.dtos.question_response import QuestionResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class RetrievalController:
    async def search_fragments(self,
                               question_request: QuestionRequest,
                               retrieval_service: RetrievalService = Depends(get_retrieval_service),
                              db: Session = Depends(get_db_session)) -> QuestionResponse:
        try:
            fragments = retrieval_service.process_question(question_request.question, db)
            fragments_response = [
                FragmentResponse.from_orm(fragment) for fragment in fragments
            ]
            return QuestionResponse(fragments=fragments_response)

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

controller = RetrievalController()
router.post("", response_model=QuestionResponse)(controller.search_fragments)