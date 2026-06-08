from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.graph_extraction.extract_entities_relations_request import (
    ExtractEntitiesRelationsRequest,
)
from app.domain.dtos.processing.graph_extraction.extract_entities_relations_response import (
    ExtractEntitiesRelationsResponse,
)


class GraphExtractionServiceInterface(ABC):
    @abstractmethod
    async def extract_entities_relations(
            self,
            extract_entities_relations_request: ExtractEntitiesRelationsRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ExtractEntitiesRelationsResponse:
        pass
