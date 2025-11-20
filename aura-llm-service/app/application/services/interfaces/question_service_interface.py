from typing import Protocol

from app.domain.dtos.question_request import QuestionRequest
from app.domain.dtos.question_response import QuestionResponse


class QuestionServiceInterface(Protocol):
    async def generate_response(self,
                                request: QuestionRequest) -> QuestionResponse:
        ...
