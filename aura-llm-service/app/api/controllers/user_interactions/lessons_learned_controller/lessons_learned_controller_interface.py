from abc import ABC, abstractmethod
from starlette.responses import StreamingResponse

from app.application.services.user_interactions.lessons_learned_service.interfaces.lessons_learned_service_interface import (
    LessonsLearnedServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.lessons_learned.lessons_learned_request import LessonsLearnedGenerateRequest
from app.domain.dtos.user_interactions.lessons_learned.lessons_learned_response import LessonsLearnedGenerateResponse


class LessonsLearnedControllerInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            lessons_learned_request: LessonsLearnedGenerateRequest,
            lessons_learned_service: LessonsLearnedServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> LessonsLearnedGenerateResponse:
        pass

    @abstractmethod
    async def generate_stream(
            self,
            lessons_learned_request: LessonsLearnedGenerateRequest,
            lessons_learned_service: LessonsLearnedServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> StreamingResponse:
        pass
