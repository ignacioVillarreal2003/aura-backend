from pydantic import BaseModel, Field

from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_entity.graph_relation_response import GraphRelationResponse


class GraphContextFact(BaseModel):
    """A single human-readable statement derived from the graph, with provenance."""

    text: str = Field(..., min_length=1)
    source_document_ids: list[int] = Field(default_factory=list)


class GraphContextResponse(BaseModel):
    """Compact graph context ready to be injected into a RAG prompt.

    ``context_text`` is the pre-rendered, length-capped block callers can
    append directly to an LLM prompt; ``entities``/``relations`` carry the
    structured form for clients that prefer to render their own view.
    """

    entities: list[GraphEntityResponse] = Field(default_factory=list)
    relations: list[GraphRelationResponse] = Field(default_factory=list)
    facts: list[GraphContextFact] = Field(default_factory=list)
    context_text: str = Field(default="")
    matched_terms: list[str] = Field(default_factory=list)
