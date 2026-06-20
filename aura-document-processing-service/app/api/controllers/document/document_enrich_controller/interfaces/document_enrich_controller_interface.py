from abc import ABC, abstractmethod

from app.domain.dtos.document.bulk.bulk_responses import BulkJobStatusResponse, BulkStartResponse
from app.domain.dtos.document.enrich.enrich_request import EnrichRequest


class DocumentEnrichControllerInterface(ABC):
    @abstractmethod
    async def enrich_manage(
            self,
            request: EnrichRequest,
    ) -> BulkStartResponse:
        pass

    @abstractmethod
    async def status_manage(self) -> BulkJobStatusResponse:
        pass

    @abstractmethod
    async def stop_manage(self) -> BulkJobStatusResponse:
        pass
