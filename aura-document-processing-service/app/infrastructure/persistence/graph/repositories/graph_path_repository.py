import logging
from typing import Any, Optional
from neo4j.exceptions import Neo4jError

from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_path.graph_path_response import GraphPath
from app.infrastructure.persistence.graph.neo4j_manager.interfaces.neo4j_manager_interface import Neo4jManagerInterface
from app.infrastructure.persistence.graph.repositories.interfaces.graph_path_repository_interface import (
    GraphPathRepositoryInterface,
)
from app.infrastructure.persistence.graph.repositories.graph_record_mappers import (
    map_entity_node,
    map_relationship,
)
from app.infrastructure.persistence.graph.repositories.exceptions.graph_repository_exceptions import \
    GraphPersistenceException

logger = logging.getLogger(__name__)

_FIND_PATHS_CYPHER_TEMPLATE = """
MATCH (a:Entity {{canonical_name: $source_name}})
WHERE ($source_type IS NULL OR a.type = $source_type)
  AND any(d IN coalesce(a.source_document_ids, []) WHERE d IN $accessible_ids)
MATCH (b:Entity {{canonical_name: $target_name}})
WHERE ($target_type IS NULL OR b.type = $target_type)
  AND any(d IN coalesce(b.source_document_ids, []) WHERE d IN $accessible_ids)
WITH a, b
{path_match}
WHERE all(n IN nodes(p)
            WHERE any(d IN coalesce(n.source_document_ids, []) WHERE d IN $accessible_ids))
  AND all(r IN relationships(p)
            WHERE any(d IN coalesce(r.source_document_ids, []) WHERE d IN $accessible_ids))
WITH p, length(p) AS hops
ORDER BY hops ASC
LIMIT $max_paths
RETURN [n IN nodes(p) | n] AS path_nodes,
       [r IN relationships(p) | r] AS path_rels,
       hops
"""

_SHORTEST_PATH_CLAUSE = "MATCH p = shortestPath((a)-[:REL*1..{max_hops}]-(b))"
_ALL_SIMPLE_PATHS_CLAUSE = "MATCH p = (a)-[:REL*1..{max_hops}]-(b)"
_MAX_ALL_SIMPLE_PATHS_HOPS = 4


class GraphPathRepository(GraphPathRepositoryInterface):
    def __init__(
            self,
            neo4j_manager: Neo4jManagerInterface,
            *,
            absolute_max_hops: int = 6,
    ) -> None:
        self._neo4j_manager = neo4j_manager
        self._absolute_max_hops = max(1, min(absolute_max_hops, 10))

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
        if not accessible_document_ids:
            return []
        hops_ceiling = self._absolute_max_hops if only_shortest else min(self._absolute_max_hops,
                                                                         _MAX_ALL_SIMPLE_PATHS_HOPS)
        clamped_hops = max(1, min(int(max_hops), hops_ceiling))
        path_match = (
            _SHORTEST_PATH_CLAUSE.format(max_hops=clamped_hops)
            if only_shortest
            else _ALL_SIMPLE_PATHS_CLAUSE.format(max_hops=clamped_hops)
        )
        cypher = _FIND_PATHS_CYPHER_TEMPLATE.format(path_match=path_match)
        params = {
            "source_name": source_canonical_name,
            "source_type": source_type.value if source_type is not None else None,
            "target_name": target_canonical_name,
            "target_type": target_type.value if target_type is not None else None,
            "max_paths": int(max_paths),
            "accessible_ids": accessible_document_ids,
        }
        try:
            records = await self._neo4j_manager.execute_read(cypher, params)
        except Neo4jError as e:
            logger.exception(
                "Neo4j error while finding paths between entities.",
                extra={
                    "source_name": source_canonical_name,
                    "target_name": target_canonical_name,
                    "max_hops": clamped_hops,
                    "neo4j_code": getattr(e, "code", None),
                },
            )
            raise GraphPersistenceException(
                "Failed to find paths in the knowledge graph."
            ) from e

        return [self._build_path(record) for record in records]

    @staticmethod
    def _build_path(record: dict[str, Any]) -> GraphPath:
        node_payloads: list[Any] = list(record.get("path_nodes") or [])
        rel_payloads: list[Any] = list(record.get("path_rels") or [])

        if len(node_payloads) < 2 or not rel_payloads:
            raise GraphPersistenceException(
                "Path record from Neo4j is malformed (insufficient nodes or relations)."
            )

        nodes = [map_entity_node(node) for node in node_payloads]
        relations = []
        for idx, rel_payload in enumerate(rel_payloads):
            relations.append(
                map_relationship(rel_payload, nodes[idx], nodes[idx + 1])
            )

        try:
            hops = int(record.get("hops") or len(rel_payloads))
        except (TypeError, ValueError):
            hops = len(rel_payloads)

        return GraphPath(
            nodes=nodes,
            relations=relations,
            length=hops,
        )
