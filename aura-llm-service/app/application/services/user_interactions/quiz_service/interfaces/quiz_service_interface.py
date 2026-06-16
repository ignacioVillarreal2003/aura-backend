from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.quiz.quiz_request import QuizGenerateRequest
from app.domain.dtos.user_interactions.quiz.quiz_response import QuizGenerateResponse
from app.domain.dtos.user_interactions.quiz.quiz_stream_events import QuizStreamEvent


class QuizServiceInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            request: QuizGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> QuizGenerateResponse:
        pass

    @abstractmethod
    async def generate_stream(
            self,
            request: QuizGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[QuizStreamEvent]:
        pass
