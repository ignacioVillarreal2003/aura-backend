from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.report.report_request import ReportGenerateRequest
from app.domain.dtos.report.report_response import ReportGenerateResponse


class ReportServiceInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            request: ReportGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ReportGenerateResponse:
        ...
