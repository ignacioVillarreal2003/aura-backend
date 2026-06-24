import logging
from neo4j.exceptions import Neo4jError

from app.domain.dtos.graph.graph_stats.graph_stats_response import GraphStatsResponse
from app.infrastructure.persistence.graph.neo4j_manager.interfaces.neo4j_manager_interface import Neo4jManagerInterface
from app.infrastructure.persistence.graph.repositories.exceptions.graph_repository_exceptions import \
    GraphPersistenceException
from app.infrastructure.persistence.graph.repositories.interfaces.graph_stats_repository_interface import (
    GraphStatsRepositoryInterface,
)

logger = logging.getLogger(__name__)

_COUNT_RELATIONS_CYPHER = """
MATCH ()-[r:REL]->()
RETURN count(r) AS total
"""

_COUNT_ENTITIES_BY_TYPE_CYPHER = """
MATCH (e:Entity)
RETURN e.type AS type, count(e) AS cnt
"""

_COUNT_INDEXED_DOCUMENTS_CYPHER = """
MATCH (e:Entity)
WHERE size(coalesce(e.source_document_ids, [])) > 0
UNWIND e.source_document_ids AS doc_id
RETURN count(DISTINCT doc_id) AS total
"""


class GraphStatsRepository(GraphStatsRepositoryInterface):
    def __init__(self, *, neo4j_manager: Neo4jManagerInterface) -> None:
        self._neo4j_manager = neo4j_manager

    async def get_stats(self) -> GraphStatsResponse:
        try:
            by_type_records = await self._neo4j_manager.execute_read(_COUNT_ENTITIES_BY_TYPE_CYPHER)
            relations_records = await self._neo4j_manager.execute_read(_COUNT_RELATIONS_CYPHER)
            docs_records = await self._neo4j_manager.execute_read(_COUNT_INDEXED_DOCUMENTS_CYPHER)
        except Neo4jError as exc:
            raise GraphPersistenceException(
                "Failed to fetch knowledge graph statistics."
            ) from exc

        entities_by_type: dict[str, int] = {}
        total_entities = 0
        for record in by_type_records:
            entity_type = str(record.get("type", "unknown"))
            count = int(record.get("cnt", 0))
            entities_by_type[entity_type] = count
            total_entities += count

        total_relations = int(relations_records[0]["total"]) if relations_records else 0
        total_documents_indexed = int(docs_records[0]["total"]) if docs_records else 0

        return GraphStatsResponse(
            total_entities=total_entities,
            total_relations=total_relations,
            entities_by_type=entities_by_type,
            total_documents_indexed=total_documents_indexed,
        )
