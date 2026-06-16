from abc import ABC, abstractmethod
from starlette.responses import StreamingResponse

from app.application.services.user_interactions.timeline_service.interfaces.timeline_service_interface import (
    TimelineServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.timeline.timeline_request import TimelineGenerateRequest
from app.domain.dtos.user_interactions.timeline.timeline_response import TimelineGenerateResponse


class TimelineControllerInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            timeline_request: TimelineGenerateRequest,
            timeline_service: TimelineServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> TimelineGenerateResponse:
        pass

    @abstractmethod
    async def generate_stream(
            self,
            timeline_request: TimelineGenerateRequest,
            timeline_service: TimelineServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> StreamingResponse:
        pass
