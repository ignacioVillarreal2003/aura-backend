from abc import ABC, abstractmethod

from app.domain.dtos.document.bulk.bulk_responses import BulkJobStatusResponse, BulkStartResponse
from app.domain.dtos.document.reprocess.reprocess_request import ReprocessRequest


class DocumentReprocessControllerInterface(ABC):
    @abstractmethod
    async def reprocess_manage(
            self,
            request: ReprocessRequest,
    ) -> BulkStartResponse:
        pass

    @abstractmethod
    async def status_manage(self) -> BulkJobStatusResponse:
        pass

    @abstractmethod
    async def stop_manage(self) -> BulkJobStatusResponse:
        pass
