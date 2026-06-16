from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.report.report_request import ReportGenerateRequest
from app.domain.dtos.user_interactions.report.report_response import ReportGenerateResponse
from app.domain.dtos.user_interactions.report.report_stream_events import ReportStreamEvent


class ReportServiceInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            request: ReportGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ReportGenerateResponse:
        pass

    @abstractmethod
    async def generate_stream(
            self,
            request: ReportGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[ReportStreamEvent]:
        pass
