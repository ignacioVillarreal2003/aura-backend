from abc import ABC, abstractmethod
from typing import Optional

from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_search.graph_search_response import GraphSearchResponse


class GraphSearchControllerInterface(ABC):
    @abstractmethod
    async def search(
            self,
            q: str,
            entity_type: Optional[EntityType],
            limit: int,
    ) -> GraphSearchResponse:
        pass
