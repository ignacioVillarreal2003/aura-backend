from abc import ABC, abstractmethod
from typing import Optional

from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_path.graph_path_response import GraphPath


class GraphPathRepositoryInterface(ABC):
    @abstractmethod
    async def find_paths(
            self,
            *,
            source_canonical_name: str,
            source_type: Optional[EntityType],
            target_canonical_name: str,
            target_type: Optional[EntityType],
            max_hops: int,
            max_paths: int,
            only_shortest: bool,
            accessible_document_ids: list[int],
    ) -> list[GraphPath]:
        pass
