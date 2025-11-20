from typing import Protocol

from app.application.services.question_service import QuestionService
from app.domain.dtos.question_request import QuestionRequest
from app.domain.dtos.question_response import QuestionResponse


class QuestionControllerInterface(Protocol):
    async def generate_response(self,
                                request: QuestionRequest,
                                question_service: QuestionService) -> QuestionResponse:
        ...
