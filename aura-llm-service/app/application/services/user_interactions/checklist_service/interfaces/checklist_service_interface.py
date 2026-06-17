from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.checklist.checklist_request import ChecklistGenerateRequest
from app.domain.dtos.user_interactions.checklist.checklist_response import ChecklistGenerateResponse
from app.domain.dtos.user_interactions.checklist.checklist_stream_events import ChecklistStreamEvent


class ChecklistServiceInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            request: ChecklistGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ChecklistGenerateResponse:
        pass

    @abstractmethod
    async def generate_stream(
            self,
            request: ChecklistGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[ChecklistStreamEvent]:
        pass
