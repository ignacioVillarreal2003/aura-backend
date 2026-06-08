from abc import ABC, abstractmethod

from app.domain.dtos.graph.graph_extraction.graph_extraction_progress import (
    GraphExtractionProgressResponse,
)
from app.domain.dtos.graph.graph_extraction.graph_reextract_request import GraphReextractRequest
from app.domain.dtos.graph.graph_extraction.graph_reextract_response import GraphReextractResponse


class GraphExtractionControllerInterface(ABC):
    @abstractmethod
    async def get_extraction_progress(
            self,
            document_id: int,
    ) -> GraphExtractionProgressResponse:
        pass

    @abstractmethod
    async def reextract(
            self,
            request: GraphReextractRequest,
    ) -> GraphReextractResponse:
        pass
