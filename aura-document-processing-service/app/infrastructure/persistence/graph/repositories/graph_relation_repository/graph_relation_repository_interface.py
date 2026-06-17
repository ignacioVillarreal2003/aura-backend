from abc import ABC, abstractmethod
from typing import Optional

from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_entity.graph_relation_response import GraphRelationResponse
from app.domain.dtos.graph.graph_extraction.graph_upsert_items import RelationUpsertItem


class GraphRelationRepositoryInterface(ABC):
    @abstractmethod
    async def upsert_relation(
            self,
            *,
            source_canonical_name: str,
            source_type: EntityType,
            target_canonical_name: str,
            target_type: EntityType,
            relation_type: str,
            confidence: float,
            document_id: int,
            fragment_id: int,
    ) -> None:
        pass

    @abstractmethod
    async def upsert_relations(
            self,
            *,
            relations: list[RelationUpsertItem],
            document_id: int,
            fragment_id: int,
    ) -> None:
        pass

    @abstractmethod
    async def delete_document_relations(
            self,
            *,
            document_id: int,
    ) -> int:
        pass

    @abstractmethod
    async def list_neighbors_of(
            self,
            *,
            canonical_name: str,
            entity_type: Optional[EntityType],
            depth: int,
            relation_types: Optional[list[str]],
            accessible_document_ids: list[int],
            limit: int,
    ) -> list[GraphRelationResponse]:
        pass

    @abstractmethod
    async def list_by_document(
            self,
            *,
            document_id: int,
            accessible_document_ids: list[int],
            limit: int,
    ) -> list[GraphRelationResponse]:
        pass
