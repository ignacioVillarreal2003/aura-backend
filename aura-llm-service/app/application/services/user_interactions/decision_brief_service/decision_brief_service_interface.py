from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.decision_brief.decision_brief_request import DecisionBriefGenerateRequest
from app.domain.dtos.user_interactions.decision_brief.decision_brief_response import DecisionBriefGenerateResponse
from app.domain.dtos.user_interactions.decision_brief.decision_brief_stream_events import DecisionBriefStreamEvent


class DecisionBriefServiceInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            request: DecisionBriefGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DecisionBriefGenerateResponse:
        pass

    @abstractmethod
    async def generate_stream(
            self,
            request: DecisionBriefGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[DecisionBriefStreamEvent]:
        pass
