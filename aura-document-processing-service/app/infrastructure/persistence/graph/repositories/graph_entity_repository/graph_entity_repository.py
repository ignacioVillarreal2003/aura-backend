import logging
from typing import Optional
from neo4j.exceptions import Neo4jError

from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.infrastructure.persistence.graph.neo4j_manager.neo4j_manager_interface import Neo4jManagerInterface
from app.infrastructure.persistence.graph.repositories.graph_entity_repository.graph_entity_repository_interface import (
    GraphEntityRepositoryInterface,
)
from app.infrastructure.persistence.graph.repositories.graph_record_mappers import map_entity_node
from app.infrastructure.persistence.graph.repositories.graph_repository_exceptions import GraphPersistenceException

logger = logging.getLogger(__name__)

_UPSERT_ENTITY_CYPHER = """
MERGE (e:Entity {canonical_name: $canonical_name, type: $entity_type})
ON CREATE SET
    e.display_name = $display_name,
    e.aliases = $aliases,
    e.description = $description,
    e.source_document_ids = [$document_id],
    e.source_fragment_ids = [$fragment_id],
    e.created_at = datetime(),
    e.updated_at = datetime()
ON MATCH SET
    e.display_name = coalesce(e.display_name, $display_name),
    e.aliases = apoc.coll.toSet(coalesce(e.aliases, []) + $aliases),
    e.description = coalesce(e.description, $description),
    e.source_document_ids = apoc.coll.toSet(coalesce(e.source_document_ids, []) + [$document_id]),
    e.source_fragment_ids = apoc.coll.toSet(coalesce(e.source_fragment_ids, []) + [$fragment_id]),
    e.updated_at = datetime()
"""

_FIND_ENTITY_BY_NAME_CYPHER = """
MATCH (e:Entity {canonical_name: $canonical_name})
WHERE ($entity_type IS NULL OR e.type = $entity_type)
  AND any(d IN coalesce(e.source_document_ids, []) WHERE d IN $accessible_ids)
RETURN e
LIMIT 1
"""

_SEARCH_ENTITY_BY_PREFIX_CYPHER = """
MATCH (e:Entity)
WHERE e.canonical_name STARTS WITH $canonical_prefix
  AND ($entity_type IS NULL OR e.type = $entity_type)
  AND any(d IN coalesce(e.source_document_ids, []) WHERE d IN $accessible_ids)
RETURN e
ORDER BY e.canonical_name ASC
LIMIT $limit
"""

_LIST_BY_TYPE_CYPHER = """
MATCH (e:Entity {type: $entity_type})
WHERE any(d IN coalesce(e.source_document_ids, []) WHERE d IN $accessible_ids)
RETURN e
ORDER BY e.canonical_name ASC
LIMIT $limit
"""


class GraphEntityRepository(GraphEntityRepositoryInterface):
    def __init__(self, neo4j_manager: Neo4jManagerInterface) -> None:
        self._neo4j_manager = neo4j_manager

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
        params = {
            "canonical_name": canonical_name,
            "display_name": display_name,
            "entity_type": entity_type.value,
            "aliases": aliases,
            "description": description,
            "document_id": document_id,
            "fragment_id": fragment_id,
        }
        try:
            await self._neo4j_manager.execute_write(_UPSERT_ENTITY_CYPHER, params)
        except Neo4jError as e:
            logger.exception(
                "Neo4j error while upserting an entity.",
                extra={
                    "canonical_name": canonical_name,
                    "entity_type": entity_type.value,
                    "document_id": document_id,
                    "fragment_id": fragment_id,
                    "neo4j_code": getattr(e, "code", None),
                },
            )
            raise GraphPersistenceException(
                "Failed to upsert an entity in the knowledge graph."
            ) from e

    async def find_by_name(
            self,
            *,
            canonical_name: str,
            entity_type: Optional[EntityType],
            accessible_document_ids: list[int],
    ) -> Optional[GraphEntityResponse]:
        if not accessible_document_ids:
            return None
        params = {
            "canonical_name": canonical_name,
            "entity_type": entity_type.value if entity_type is not None else None,
            "accessible_ids": accessible_document_ids,
        }
        try:
            records = await self._neo4j_manager.execute_read(
                _FIND_ENTITY_BY_NAME_CYPHER, params
            )
        except Neo4jError as e:
            logger.exception(
                "Neo4j error while looking up an entity by name.",
                extra={
                    "canonical_name": canonical_name,
                    "neo4j_code": getattr(e, "code", None),
                },
            )
            raise GraphPersistenceException(
                "Failed to look up an entity in the knowledge graph."
            ) from e
        if not records:
            return None
        return map_entity_node(records[0]["e"])

    async def search_by_name_prefix(
            self,
            *,
            canonical_prefix: str,
            entity_type: Optional[EntityType],
            accessible_document_ids: list[int],
            limit: int,
    ) -> list[GraphEntityResponse]:
        if not accessible_document_ids:
            return []
        params = {
            "canonical_prefix": canonical_prefix,
            "entity_type": entity_type.value if entity_type is not None else None,
            "accessible_ids": accessible_document_ids,
            "limit": int(limit),
        }
        try:
            records = await self._neo4j_manager.execute_read(
                _SEARCH_ENTITY_BY_PREFIX_CYPHER, params
            )
        except Neo4jError as e:
            logger.exception(
                "Neo4j error while searching entities by prefix.",
                extra={"prefix_length": len(canonical_prefix)},
            )
            raise GraphPersistenceException(
                "Failed to search entities in the knowledge graph."
            ) from e
        return [map_entity_node(record["e"]) for record in records]

    async def list_by_type(
            self,
            *,
            entity_type: EntityType,
            accessible_document_ids: list[int],
            limit: int,
    ) -> list[GraphEntityResponse]:
        if not accessible_document_ids:
            return []
        params = {
            "entity_type": entity_type.value,
            "accessible_ids": accessible_document_ids,
            "limit": int(limit),
        }
        try:
            records = await self._neo4j_manager.execute_read(
                _LIST_BY_TYPE_CYPHER, params
            )
        except Neo4jError as e:
            logger.exception(
                "Neo4j error while listing entities by type.",
                extra={"entity_type": entity_type.value},
            )
            raise GraphPersistenceException(
                "Failed to list entities in the knowledge graph."
            ) from e
        return [map_entity_node(record["e"]) for record in records]
