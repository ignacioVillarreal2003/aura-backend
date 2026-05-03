from typing import Optional
from pydantic import BaseModel, Field

from app.domain.constants.graph.query_intent import QueryIntent
from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_entity.graph_relation_response import GraphRelationResponse
from app.domain.dtos.graph.graph_field_limits import MAX_QUERY_RESULTS


class GraphQueryResponse(BaseModel):
    intent: QueryIntent = Field(...)
    confidence: float = Field(..., ge=0.0, le=1.0)
    entities: list[GraphEntityResponse] = Field(
        default_factory=list, max_length=MAX_QUERY_RESULTS
    )
    relations: list[GraphRelationResponse] = Field(
        default_factory=list, max_length=MAX_QUERY_RESULTS
    )
    explanation: Optional[str] = Field(default=None, max_length=2_000)
