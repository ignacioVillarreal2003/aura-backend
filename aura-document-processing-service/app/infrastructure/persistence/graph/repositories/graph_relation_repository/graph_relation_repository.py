import logging
from typing import Optional
from neo4j.exceptions import Neo4jError

from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_entity.graph_relation_response import GraphRelationResponse
from app.infrastructure.persistence.graph.neo4j_manager.neo4j_manager_interface import Neo4jManagerInterface
from app.infrastructure.persistence.graph.repositories.graph_record_mappers import (
    map_entity_node,
    map_relationship,
)
from app.infrastructure.persistence.graph.repositories.graph_relation_repository.graph_relation_repository_interface import (
    GraphRelationRepositoryInterface,
)
from app.infrastructure.persistence.graph.repositories.graph_repository_exceptions import GraphPersistenceException

logger = logging.getLogger(__name__)

_UPSERT_RELATION_CYPHER = """
MATCH (a:Entity {canonical_name: $source_name, type: $source_type})
MATCH (b:Entity {canonical_name: $target_name, type: $target_type})
MERGE (a)-[r:REL {type: $relation_type}]->(b)
ON CREATE SET
    r.source_document_ids = [$document_id],
    r.evidence_fragment_ids = [$fragment_id],
    r.confidence = $confidence,
    r.created_at = datetime(),
    r.updated_at = datetime()
ON MATCH SET
    r.source_document_ids = apoc.coll.toSet(coalesce(r.source_document_ids, []) + [$document_id]),
    r.evidence_fragment_ids = apoc.coll.toSet(coalesce(r.evidence_fragment_ids, []) + [$fragment_id]),
    r.confidence = CASE
        WHEN $confidence > coalesce(r.confidence, 0.0) THEN $confidence
        ELSE r.confidence
    END,
    r.updated_at = datetime()
"""

_LIST_NEIGHBORS_CYPHER_TEMPLATE = """
MATCH (center:Entity {{canonical_name: $canonical_name}})
WHERE ($entity_type IS NULL OR center.type = $entity_type)
  AND any(d IN coalesce(center.source_document_ids, []) WHERE d IN $accessible_ids)
MATCH path = (center)-[rels:REL*1..{depth}]-(neighbor:Entity)
WHERE all(r IN rels WHERE
            ($relation_types IS NULL OR r.type IN $relation_types)
            AND any(d IN coalesce(r.source_document_ids, []) WHERE d IN $accessible_ids)
        )
  AND any(d IN coalesce(neighbor.source_document_ids, []) WHERE d IN $accessible_ids)
WITH path, rels, center, neighbor
UNWIND range(0, size(rels) - 1) AS idx
WITH path, rels[idx] AS rel, nodes(path)[idx] AS source_node, nodes(path)[idx + 1] AS target_node
RETURN DISTINCT rel, source_node, target_node
LIMIT $limit
"""


class GraphRelationRepository(GraphRelationRepositoryInterface):
    def __init__(
            self,
            neo4j_manager: Neo4jManagerInterface,
            *,
            max_depth: int = 4,
    ) -> None:
        self._neo4j_manager = neo4j_manager
        self._max_depth = max(1, min(max_depth, 6))

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
        params = {
            "source_name": source_canonical_name,
            "source_type": source_type.value,
            "target_name": target_canonical_name,
            "target_type": target_type.value,
            "relation_type": relation_type,
            "confidence": float(max(0.0, min(1.0, confidence))),
            "document_id": document_id,
            "fragment_id": fragment_id,
        }
        try:
            await self._neo4j_manager.execute_write(_UPSERT_RELATION_CYPHER, params)
        except Neo4jError as e:
            logger.exception(
                "Neo4j error while upserting a relation.",
                extra={
                    "source": source_canonical_name,
                    "target": target_canonical_name,
                    "relation_type": relation_type,
                    "document_id": document_id,
                    "fragment_id": fragment_id,
                    "neo4j_code": getattr(e, "code", None),
                },
            )
            raise GraphPersistenceException(
                "Failed to upsert a relation in the knowledge graph."
            ) from e

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
        if not accessible_document_ids:
            return []
        clamped_depth = max(1, min(int(depth), self._max_depth))
        cypher = _LIST_NEIGHBORS_CYPHER_TEMPLATE.format(depth=clamped_depth)
        params = {
            "canonical_name": canonical_name,
            "entity_type": entity_type.value if entity_type is not None else None,
            "relation_types": relation_types,
            "accessible_ids": accessible_document_ids,
            "limit": int(limit),
        }
        try:
            records = await self._neo4j_manager.execute_read(cypher, params)
        except Neo4jError as e:
            logger.exception(
                "Neo4j error while listing neighbors.",
                extra={
                    "canonical_name": canonical_name,
                    "depth": clamped_depth,
                    "neo4j_code": getattr(e, "code", None),
                },
            )
            raise GraphPersistenceException(
                "Failed to list neighbors in the knowledge graph."
            ) from e

        out: list[GraphRelationResponse] = []
        for record in records:
            source_entity = map_entity_node(record["source_node"])
            target_entity = map_entity_node(record["target_node"])
            out.append(map_relationship(record["rel"], source_entity, target_entity))
        return out
