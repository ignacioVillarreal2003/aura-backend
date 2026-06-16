from abc import ABC, abstractmethod
from starlette.responses import StreamingResponse

from app.application.services.user_interactions.quiz_service.interfaces.quiz_service_interface import QuizServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.quiz.quiz_request import QuizGenerateRequest
from app.domain.dtos.user_interactions.quiz.quiz_response import QuizGenerateResponse


class QuizControllerInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            quiz_request: QuizGenerateRequest,
            quiz_service: QuizServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> QuizGenerateResponse:
        pass

    @abstractmethod
    async def generate_stream(
            self,
            quiz_request: QuizGenerateRequest,
            quiz_service: QuizServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> StreamingResponse:
        pass
