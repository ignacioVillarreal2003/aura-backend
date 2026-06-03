from pydantic import BaseModel, Field

from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_field_limits import MAX_QUERY_RESULTS


class GraphSearchResponse(BaseModel):
    results: list[GraphEntityResponse] = Field(
        default_factory=list,
        max_length=MAX_QUERY_RESULTS,
        description="Entities matching the search query, ordered by relevance.",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Number of results returned (may be capped by limit).",
    )
    has_more: bool = Field(
        default=False,
        description="True when results were capped by limit; more entities may exist.",
    )
