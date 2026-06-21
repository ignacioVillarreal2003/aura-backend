from abc import ABC, abstractmethod

from app.domain.dtos.document.bulk.bulk_responses import BulkJobStatusResponse, BulkStartResponse
from app.domain.dtos.graph.graph_extraction.graph_reextract_request import GraphReextractRequest


class GraphExtractionControllerInterface(ABC):
    @abstractmethod
    async def extract_manage(
            self,
            request: GraphReextractRequest,
    ) -> BulkStartResponse:
        pass

    @abstractmethod
    async def status_manage(self) -> BulkJobStatusResponse:
        pass

    @abstractmethod
    async def stop_manage(self) -> BulkJobStatusResponse:
        pass
