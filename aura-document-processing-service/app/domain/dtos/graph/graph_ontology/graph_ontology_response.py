from pydantic import BaseModel, Field

from app.domain.dtos.graph.graph_field_limits import (
    MAX_ONTOLOGY_ENTITY_TYPES,
    MAX_ONTOLOGY_RELATION_TYPES,
)


class GraphOntologyResponse(BaseModel):
    entity_types: list[str] = Field(
        ...,
        max_length=MAX_ONTOLOGY_ENTITY_TYPES,
        description="Entity type values active in this deployment (lowercase).",
    )
    relation_types: list[str] = Field(
        ...,
        max_length=MAX_ONTOLOGY_RELATION_TYPES,
        description="Relation type values active in this deployment (lowercase).",
    )
    query_max_results: int = Field(
        ...,
        ge=1,
        description="Maximum number of entities/relations returned per query.",
    )
    query_max_depth: int = Field(
        ...,
        ge=1,
        description="Maximum neighbor traversal depth supported by this deployment.",
    )
