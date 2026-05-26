from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.checklist.checklist_request import ChecklistGenerateRequest
from app.domain.dtos.checklist.checklist_response import ChecklistGenerateResponse


class ChecklistServiceInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            request: ChecklistGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ChecklistGenerateResponse:
        ...
