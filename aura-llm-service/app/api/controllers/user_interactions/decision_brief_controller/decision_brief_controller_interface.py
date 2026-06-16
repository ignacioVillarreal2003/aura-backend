from abc import ABC, abstractmethod
from starlette.responses import StreamingResponse

from app.application.services.user_interactions.decision_brief_service.interfaces.decision_brief_service_interface import (
    DecisionBriefServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.decision_brief.decision_brief_request import DecisionBriefGenerateRequest
from app.domain.dtos.user_interactions.decision_brief.decision_brief_response import DecisionBriefGenerateResponse


class DecisionBriefControllerInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            decision_brief_request: DecisionBriefGenerateRequest,
            decision_brief_service: DecisionBriefServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> DecisionBriefGenerateResponse:
        pass

    @abstractmethod
    async def generate_stream(
            self,
            decision_brief_request: DecisionBriefGenerateRequest,
            decision_brief_service: DecisionBriefServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> StreamingResponse:
        pass
