from typing import Protocol

from app.domain.dtos.summary_request import SummaryRequest
from app.domain.dtos.summary_response import SummaryResponse


class SummaryServiceInterface(Protocol):
    async def summarize(self,
                        request: SummaryRequest) -> SummaryResponse:
        ...
