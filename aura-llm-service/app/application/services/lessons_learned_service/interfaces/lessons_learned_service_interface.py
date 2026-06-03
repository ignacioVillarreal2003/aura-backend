from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.lessons_learned.lessons_learned_request import LessonsLearnedGenerateRequest
from app.domain.dtos.lessons_learned.lessons_learned_response import LessonsLearnedGenerateResponse


class LessonsLearnedServiceInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            request: LessonsLearnedGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> LessonsLearnedGenerateResponse:
        ...
