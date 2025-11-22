from typing import Protocol
from sqlalchemy.orm.session import Session

from app.domain.dtos.question_request import QuestionRequest
from app.domain.dtos.question_response import QuestionResponse


class RetrivalServiceInterface(Protocol):
    def process_question(self,
                         question: QuestionRequest,
                         db: Session,
                         embedder_type: str,
                         k: int,
                         threshold: float) -> QuestionResponse:
        ...
