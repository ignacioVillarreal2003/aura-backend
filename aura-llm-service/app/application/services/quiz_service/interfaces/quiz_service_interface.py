from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.quiz.quiz_request import QuizGenerateRequest
from app.domain.dtos.quiz.quiz_response import QuizGenerateResponse


class QuizServiceInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            request: QuizGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> QuizGenerateResponse:
        ...
