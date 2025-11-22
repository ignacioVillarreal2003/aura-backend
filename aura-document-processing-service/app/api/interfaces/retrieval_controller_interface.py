from typing import Protocol
from sqlalchemy.orm.session import Session

from app.application.services.retrival_service import RetrievalService
from app.domain.dtos.question_request import QuestionRequest
from app.domain.dtos.question_response import QuestionResponse


class RetrievalControllerInterface(Protocol):
    async def search_context(self,
                             question_request: QuestionRequest,
                             retrieval_service: RetrievalService ,
                             db: Session) -> QuestionResponse:
        ...