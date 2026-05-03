from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.domain.constants.graph.entity_type import EntityType
from app.domain.field_limits import MAX_ENTITY_NAME_CHARS
from app.domain.dtos.graph.graph_field_limits import MAX_RELATION_TYPE_CHARS


class GraphRelationEndpoint(BaseModel):
    canonical_name: str = Field(..., min_length=1, max_length=MAX_ENTITY_NAME_CHARS)
    display_name: str = Field(..., min_length=1, max_length=MAX_ENTITY_NAME_CHARS)
    type: EntityType = Field(...)


class GraphRelationResponse(BaseModel):
    type: str = Field(..., min_length=1, max_length=MAX_RELATION_TYPE_CHARS)
    source: GraphRelationEndpoint = Field(...)
    target: GraphRelationEndpoint = Field(...)
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_document_ids: list[int] = Field(default_factory=list)
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
