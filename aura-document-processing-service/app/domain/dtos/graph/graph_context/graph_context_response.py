from pydantic import BaseModel, Field

from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_entity.graph_relation_response import GraphRelationResponse


class GraphContextFact(BaseModel):
    text: str = Field(..., min_length=1)
    source_document_ids: list[int] = Field(default_factory=list)


class GraphContextResponse(BaseModel):
    entities: list[GraphEntityResponse] = Field(default_factory=list)
    relations: list[GraphRelationResponse] = Field(default_factory=list)
    facts: list[GraphContextFact] = Field(default_factory=list)
    context_text: str = Field(default="")
    matched_terms: list[str] = Field(default_factory=list)
