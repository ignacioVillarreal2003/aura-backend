from abc import ABC, abstractmethod
from starlette.responses import StreamingResponse

from app.application.services.user_interactions.checklist_service.interfaces.checklist_service_interface import (
    ChecklistServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.checklist.checklist_request import ChecklistGenerateRequest
from app.domain.dtos.user_interactions.checklist.checklist_response import ChecklistGenerateResponse


class ChecklistControllerInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            checklist_request: ChecklistGenerateRequest,
            checklist_service: ChecklistServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> ChecklistGenerateResponse:
        pass

    @abstractmethod
    async def generate_stream(
            self,
            checklist_request: ChecklistGenerateRequest,
            checklist_service: ChecklistServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> StreamingResponse:
        pass
