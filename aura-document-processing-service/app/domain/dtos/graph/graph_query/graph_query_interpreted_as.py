from typing import Optional

from pydantic import BaseModel, Field

from app.domain.constants.graph.query_intent import QueryIntent
from app.domain.dtos.graph.graph_field_limits import (
    MAX_ENTITY_TYPE_CHARS,
    MAX_ONTOLOGY_RELATION_TYPES,
)
from app.domain.field_limits import MAX_ENTITY_NAME_CHARS, MAX_ID


class GraphQueryInterpretedAs(BaseModel):
    intent: QueryIntent = Field(...)
    entity_name: Optional[str] = Field(
        default=None,
        max_length=MAX_ENTITY_NAME_CHARS,
        description="Resolved entity name for find_entity / find_neighbors intents.",
    )
    entity_type: Optional[str] = Field(
        default=None,
        max_length=MAX_ENTITY_TYPE_CHARS,
        description="Entity type filter applied to the query.",
    )
    source_name: Optional[str] = Field(
        default=None,
        max_length=MAX_ENTITY_NAME_CHARS,
        description="Source entity name for find_path intent.",
    )
    target_name: Optional[str] = Field(
        default=None,
        max_length=MAX_ENTITY_NAME_CHARS,
        description="Target entity name for find_path intent.",
    )
    depth: Optional[int] = Field(
        default=None,
        ge=1,
        le=6,
        description="Neighbor traversal depth for find_neighbors / find_path.",
    )
    relation_types: Optional[list[str]] = Field(
        default=None,
        max_length=MAX_ONTOLOGY_RELATION_TYPES,
        description="Relation type filters applied to find_neighbors.",
    )
    document_id: Optional[int] = Field(
        default=None,
        ge=1,
        le=MAX_ID,
        description="Document ID for list_by_document intent.",
    )
