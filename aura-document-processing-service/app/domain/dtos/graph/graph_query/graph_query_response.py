from typing import Optional
from pydantic import BaseModel, Field

from app.domain.constants.graph.query_intent import QueryIntent
from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_entity.graph_relation_response import GraphRelationResponse
from app.domain.dtos.graph.graph_field_limits import MAX_QUERY_RESULTS
from app.domain.dtos.graph.graph_query.graph_query_interpreted_as import GraphQueryInterpretedAs


class GraphQueryResponse(BaseModel):
    intent: QueryIntent = Field(...)
    confidence: float = Field(..., ge=0.0, le=1.0)
    entities: list[GraphEntityResponse] = Field(
        default_factory=list, max_length=MAX_QUERY_RESULTS
    )
    relations: list[GraphRelationResponse] = Field(
        default_factory=list, max_length=MAX_QUERY_RESULTS
    )
    nodes: list[GraphEntityResponse] = Field(
        default_factory=list,
        max_length=MAX_QUERY_RESULTS * 2,
        description=(
            "Deduplicated union of all entity nodes present in 'entities' and as "
            "endpoints of 'relations'. Ready for direct use in graph visualization "
            "libraries (React Flow, Cytoscape, D3) without client-side derivation."
        ),
    )
    explanation: Optional[str] = Field(default=None, max_length=2_000)
    interpreted_as: Optional[GraphQueryInterpretedAs] = Field(
        default=None,
        description=(
            "Structured summary of what the LLM understood from the question. "
            "Use this to show feedback to the user and allow query refinement."
        ),
    )
    has_more: bool = Field(
        default=False,
        description="True when results were capped by max_results; more records may exist.",
    )
