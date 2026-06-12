from abc import ABC, abstractmethod

from app.application.services.processing.graph_extraction_service.interfaces.graph_extraction_service_interface import (
    GraphExtractionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.graph_extraction.extract_entities_relations_request import (
    ExtractEntitiesRelationsRequest,
)
from app.domain.dtos.processing.graph_extraction.extract_entities_relations_response import (
    ExtractEntitiesRelationsResponse,
)


class GraphExtractionControllerInterface(ABC):
    @abstractmethod
    async def extract_entities_relations(
            self,
            extract_entities_relations_request: ExtractEntitiesRelationsRequest,
            graph_extraction_service: GraphExtractionServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> ExtractEntitiesRelationsResponse:
        pass
