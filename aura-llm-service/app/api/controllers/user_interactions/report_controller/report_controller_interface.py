from abc import ABC, abstractmethod
from starlette.responses import StreamingResponse

from app.application.services.user_interactions.report_service.interfaces.report_service_interface import ReportServiceInterface
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.report.report_request import ReportGenerateRequest
from app.domain.dtos.user_interactions.report.report_response import ReportGenerateResponse


class ReportControllerInterface(ABC):
    @abstractmethod
    async def generate(
            self,
            report_request: ReportGenerateRequest,
            report_service: ReportServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> ReportGenerateResponse:
        pass

    @abstractmethod
    async def generate_stream(
            self,
            report_request: ReportGenerateRequest,
            report_service: ReportServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> StreamingResponse:
        pass
