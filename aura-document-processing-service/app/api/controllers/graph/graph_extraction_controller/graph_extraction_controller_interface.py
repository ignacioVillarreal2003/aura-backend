from abc import ABC, abstractmethod

from app.domain.dtos.document.bulk.bulk_responses import BulkJobStatusResponse, BulkStartResponse
from app.domain.dtos.graph.graph_extraction.graph_extraction_progress import (
    GraphExtractionProgressResponse,
)
from app.domain.dtos.graph.graph_extraction.graph_reextract_request import GraphReextractRequest


class GraphExtractionControllerInterface(ABC):
    @abstractmethod
    async def get_extraction_progress(
            self,
            document_id: int,
    ) -> GraphExtractionProgressResponse:
        ...

    @abstractmethod
    async def reextract(
            self,
            request: GraphReextractRequest,
    ) -> BulkStartResponse:
        ...

    @abstractmethod
    async def batch_status(self) -> BulkJobStatusResponse:
        ...

    @abstractmethod
    async def stop(self) -> BulkJobStatusResponse:
        ...
