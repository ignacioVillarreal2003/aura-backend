from pydantic import BaseModel, Field

from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_entity.graph_relation_response import GraphRelationResponse
from app.domain.dtos.graph.graph_field_limits import MAX_QUERY_RESULTS


class GraphEntityWithRelationsResponse(BaseModel):
    entity: GraphEntityResponse = Field(...)
    relations: list[GraphRelationResponse] = Field(
        default_factory=list, max_length=MAX_QUERY_RESULTS
    )
