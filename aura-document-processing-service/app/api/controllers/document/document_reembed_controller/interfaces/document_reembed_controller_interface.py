from abc import ABC, abstractmethod

from app.domain.dtos.document.bulk.bulk_responses import BulkJobStatusResponse, BulkStartResponse
from app.domain.dtos.document.reembed.reembed_request import ReembedRequest


class DocumentReembedControllerInterface(ABC):
    @abstractmethod
    async def reembed_manage(
            self,
            request: ReembedRequest,
    ) -> BulkStartResponse:
        ...

    @abstractmethod
    async def status_manage(self) -> BulkJobStatusResponse:
        ...

    @abstractmethod
    async def stop_manage(self) -> BulkJobStatusResponse:
        ...
