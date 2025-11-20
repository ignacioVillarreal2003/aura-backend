from typing import Protocol

from app.application.services.summary_service import SummaryService
from app.domain.dtos.summary_request import SummaryRequest
from app.domain.dtos.summary_response import SummaryResponse


class SummaryControllerInterface(Protocol):
    async def summarize(self,
                        request: SummaryRequest,
                        summary_service: SummaryService) -> SummaryResponse:
        ...
