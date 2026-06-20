from abc import ABC, abstractmethod
from typing import Optional

from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_extraction.graph_upsert_items import EntityUpsertItem


class GraphEntityRepositoryInterface(ABC):
    @abstractmethod
    async def upsert_entity(
            self,
            *,
            canonical_name: str,
            display_name: str,
            entity_type: EntityType,
            aliases: list[str],
            description: Optional[str],
            document_id: int,
            fragment_id: int,
    ) -> None:
        pass

    @abstractmethod
    async def upsert_entities(
            self,
            *,
            entities: list[EntityUpsertItem],
            document_id: int,
            fragment_id: int,
    ) -> None:
        pass

    @abstractmethod
    async def delete_document_entities(
            self,
            *,
            document_id: int,
    ) -> int:
        pass

    @abstractmethod
    async def find_by_name(
            self,
            *,
            canonical_name: str,
            entity_type: Optional[EntityType],
            accessible_document_ids: list[int],
    ) -> Optional[GraphEntityResponse]:
        pass

    @abstractmethod
    async def search_by_name_prefix(
            self,
            *,
            canonical_prefix: str,
            entity_type: Optional[EntityType],
            accessible_document_ids: list[int],
            limit: int,
    ) -> list[GraphEntityResponse]:
        pass

    @abstractmethod
    async def list_by_type(
            self,
            *,
            entity_type: EntityType,
            accessible_document_ids: list[int],
            limit: int,
    ) -> list[GraphEntityResponse]:
        pass

    @abstractmethod
    async def list_by_document(
            self,
            *,
            document_id: int,
            entity_type: Optional[EntityType],
            accessible_document_ids: list[int],
            limit: int,
    ) -> list[GraphEntityResponse]:
        pass

    @abstractmethod
    async def fulltext_search(
            self,
            *,
            query_string: str,
            entity_type: Optional[EntityType],
            accessible_document_ids: list[int],
            limit: int,
    ) -> list[GraphEntityResponse]:
        pass
