from pydantic import BaseModel, Field

from app.domain.dtos.graph.graph_field_limits import MAX_ONTOLOGY_ENTITY_TYPES


class GraphStatsResponse(BaseModel):
    total_entities: int = Field(..., ge=0, description="Total number of entity nodes in the knowledge graph.")
    total_relations: int = Field(..., ge=0, description="Total number of relation edges in the knowledge graph.")
    entities_by_type: dict[str, int] = Field(
        default_factory=dict,
        max_length=MAX_ONTOLOGY_ENTITY_TYPES,
        description="Count of entities broken down by entity type.",
    )
    total_documents_indexed: int = Field(
        ...,
        ge=0,
        description="Number of distinct documents that contributed at least one entity to the graph.",
    )
