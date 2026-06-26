import logging
import re
from typing import Optional
from neo4j.exceptions import Neo4jError

from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_extraction.graph_upsert_items import EntityUpsertItem
from app.infrastructure.persistence.graph.neo4j_manager.interfaces.neo4j_manager_interface import Neo4jManagerInterface
from app.infrastructure.persistence.graph.repositories.interfaces.graph_entity_repository_interface import (
    GraphEntityRepositoryInterface,
)
from app.infrastructure.persistence.graph.repositories.graph_record_mappers import map_entity_node
from app.infrastructure.persistence.graph.repositories.exceptions.graph_repository_exceptions import \
    GraphPersistenceException

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
    e.aliases = reduce(acc = coalesce(e.aliases, []), item IN $aliases |
                    CASE WHEN item IN acc THEN acc ELSE acc + [item] END),
    e.description = coalesce(e.description, $description),
    e.source_document_ids = coalesce(e.source_document_ids, []) +
                    CASE WHEN $document_id IN coalesce(e.source_document_ids, []) THEN [] ELSE [$document_id] END,
    e.source_fragment_ids = coalesce(e.source_fragment_ids, []) +
                    CASE WHEN $fragment_id IN coalesce(e.source_fragment_ids, []) THEN [] ELSE [$fragment_id] END,
    e.updated_at = datetime()
"""

_UPSERT_ENTITIES_BATCH_CYPHER = """
UNWIND $entities AS item
MERGE (e:Entity {canonical_name: item.canonical_name, type: item.entity_type})
ON CREATE SET
    e.display_name = item.display_name,
    e.aliases = item.aliases,
    e.description = item.description,
    e.source_document_ids = [$document_id],
    e.source_fragment_ids = [$fragment_id],
    e.created_at = datetime(),
    e.updated_at = datetime()
ON MATCH SET
    e.display_name = coalesce(e.display_name, item.display_name),
    e.aliases = reduce(acc = coalesce(e.aliases, []), alias IN item.aliases |
                    CASE WHEN alias IN acc THEN acc ELSE acc + [alias] END),
    e.description = coalesce(e.description, item.description),
    e.source_document_ids = coalesce(e.source_document_ids, []) +
                    CASE WHEN $document_id IN coalesce(e.source_document_ids, []) THEN [] ELSE [$document_id] END,
    e.source_fragment_ids = coalesce(e.source_fragment_ids, []) +
                    CASE WHEN $fragment_id IN coalesce(e.source_fragment_ids, []) THEN [] ELSE [$fragment_id] END,
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

_LIST_BY_DOCUMENT_CYPHER = """
MATCH (e:Entity)
WHERE $document_id IN coalesce(e.source_document_ids, [])
  AND ($entity_type IS NULL OR e.type = $entity_type)
  AND any(d IN coalesce(e.source_document_ids, []) WHERE d IN $accessible_ids)
RETURN e
ORDER BY e.canonical_name ASC
LIMIT $limit
"""

_DELETE_DOCUMENT_ENTITIES_CYPHER = """
MATCH (e:Entity)
WHERE $document_id IN coalesce(e.source_document_ids, [])
WITH e, [d IN coalesce(e.source_document_ids, []) WHERE d <> $document_id] AS remaining_docs
SET e.source_document_ids = remaining_docs,
    e.updated_at = datetime()
WITH e, remaining_docs
WHERE size(remaining_docs) = 0
DETACH DELETE e
RETURN count(e) AS deleted_count
"""

_LUCENE_SPECIAL_CHARS_PATTERN = re.compile(r'[+\-!(){}\[\]^"~*?:\\/]|&&|\|\|')
_MIN_PREFIX_TOKEN_LENGTH = 3


def build_lucene_query(raw: str) -> str:
    sanitized = _LUCENE_SPECIAL_CHARS_PATTERN.sub(" ", raw)
    tokens = [t for t in sanitized.split() if t]
    if not tokens:
        return ""
    parts = [
        f"{token}*" if len(token) >= _MIN_PREFIX_TOKEN_LENGTH else token
        for token in tokens
    ]
    return " OR ".join(parts)


_FULLTEXT_SEARCH_CYPHER = """
CALL db.index.fulltext.queryNodes("entity_fulltext", $query_string)
YIELD node AS e, score
WHERE ($entity_type IS NULL OR e.type = $entity_type)
  AND any(d IN coalesce(e.source_document_ids, []) WHERE d IN $accessible_ids)
RETURN e, score
ORDER BY score DESC
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

    async def upsert_entities(
            self,
            *,
            entities: list[EntityUpsertItem],
            document_id: int,
            fragment_id: int,
    ) -> None:
        if not entities:
            return
        params = {
            "entities": [
                {
                    "canonical_name": item.canonical_name,
                    "display_name": item.display_name,
                    "entity_type": item.entity_type.value,
                    "aliases": list(item.aliases),
                    "description": item.description,
                }
                for item in entities
            ],
            "document_id": document_id,
            "fragment_id": fragment_id,
        }
        try:
            await self._neo4j_manager.execute_write(_UPSERT_ENTITIES_BATCH_CYPHER, params)
        except Neo4jError as e:
            logger.exception(
                "Neo4j error while upserting an entity batch.",
                extra={
                    "batch_size": len(entities),
                    "document_id": document_id,
                    "fragment_id": fragment_id,
                    "neo4j_code": getattr(e, "code", None),
                },
            )
            raise GraphPersistenceException(
                "Failed to upsert an entity batch in the knowledge graph."
            ) from e

    async def delete_document_entities(
            self,
            *,
            document_id: int,
    ) -> int:
        try:
            records = await self._neo4j_manager.execute_write(
                _DELETE_DOCUMENT_ENTITIES_CYPHER, {"document_id": document_id}
            )
            deleted_count = int(records[0]["deleted_count"]) if records else 0
            logger.info(
                "Document footprint removed from the entity graph.",
                extra={"document_id": document_id, "orphaned_entities_deleted": deleted_count},
            )
            return deleted_count
        except Neo4jError as e:
            logger.exception(
                "Neo4j error while deleting a document's entities.",
                extra={"document_id": document_id, "neo4j_code": getattr(e, "code", None)},
            )
            raise GraphPersistenceException(
                "Failed to delete a document's entities from the knowledge graph."
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

    async def list_by_document(
            self,
            *,
            document_id: int,
            entity_type: Optional[EntityType],
            accessible_document_ids: list[int],
            limit: int,
    ) -> list[GraphEntityResponse]:
        if not accessible_document_ids:
            return []
        params = {
            "document_id": document_id,
            "entity_type": entity_type.value if entity_type is not None else None,
            "accessible_ids": accessible_document_ids,
            "limit": int(limit),
        }
        try:
            records = await self._neo4j_manager.execute_read(
                _LIST_BY_DOCUMENT_CYPHER, params
            )
        except Neo4jError as e:
            logger.exception(
                "Neo4j error while listing entities by document.",
                extra={"document_id": document_id, "neo4j_code": getattr(e, "code", None)},
            )
            raise GraphPersistenceException(
                "Failed to list entities by document in the knowledge graph."
            ) from e
        return [map_entity_node(record["e"]) for record in records]

    async def fulltext_search(
            self,
            *,
            query_string: str,
            entity_type: Optional[EntityType],
            accessible_document_ids: list[int],
            limit: int,
    ) -> list[GraphEntityResponse]:
        if not accessible_document_ids or not query_string.strip():
            return []
        lucene_query = build_lucene_query(query_string)
        if not lucene_query:
            return []
        params = {
            "query_string": lucene_query,
            "entity_type": entity_type.value if entity_type is not None else None,
            "accessible_ids": accessible_document_ids,
            "limit": int(limit),
        }
        try:
            records = await self._neo4j_manager.execute_read(
                _FULLTEXT_SEARCH_CYPHER, params
            )
        except Neo4jError as e:
            logger.warning(
                "Neo4j error during fulltext entity search (non-fatal).",
                extra={"neo4j_code": getattr(e, "code", None)},
            )
            return []
        return [map_entity_node(record["e"]) for record in records]
