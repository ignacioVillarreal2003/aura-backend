from pydantic import BaseModel, Field

from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_entity.graph_relation_response import GraphRelationResponse
from app.domain.field_limits import MAX_PATH_HOPS
from app.domain.dtos.graph.graph_field_limits import MAX_PATHS_RETURNED


class GraphPath(BaseModel):
    nodes: list[GraphEntityResponse] = Field(..., min_length=2, max_length=MAX_PATH_HOPS + 1)
    relations: list[GraphRelationResponse] = Field(..., min_length=1, max_length=MAX_PATH_HOPS)
    length: int = Field(..., ge=1, le=MAX_PATH_HOPS)


class FindPathResponse(BaseModel):
    paths: list[GraphPath] = Field(default_factory=list, max_length=MAX_PATHS_RETURNED)
    truncated: bool = Field(default=False)
