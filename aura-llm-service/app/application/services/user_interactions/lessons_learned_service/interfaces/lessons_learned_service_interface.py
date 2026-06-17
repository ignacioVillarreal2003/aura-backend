from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.lessons_learned.lessons_learned_request import LessonsLearnedGenerateRequest
from app.domain.dtos.user_interactions.lessons_learned.lessons_learned_response import LessonsLearnedGenerateResponse
from app.domain.dtos.user_interactions.lessons_learned.lessons_learned_stream_events import LessonsLearnedStreamEvent


class LessonsLearnedServiceInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            request: LessonsLearnedGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> LessonsLearnedGenerateResponse:
        pass

    @abstractmethod
    async def generate_stream(
            self,
            request: LessonsLearnedGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[LessonsLearnedStreamEvent]:
        pass
