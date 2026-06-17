from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.timeline.timeline_request import TimelineGenerateRequest
from app.domain.dtos.user_interactions.timeline.timeline_response import TimelineGenerateResponse
from app.domain.dtos.user_interactions.timeline.timeline_stream_events import TimelineStreamEvent


class TimelineServiceInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            request: TimelineGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> TimelineGenerateResponse:
        pass

    @abstractmethod
    async def generate_stream(
            self,
            request: TimelineGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[TimelineStreamEvent]:
        pass
