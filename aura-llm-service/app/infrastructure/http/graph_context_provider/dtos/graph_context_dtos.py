from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class GraphContextProviderRequest(BaseModel):
    """Payload sent to the document-processing /graph/context endpoint."""

    model_config = ConfigDict(frozen=True)

    question: Optional[str] = None
    terms: list[str] = Field(default_factory=list)
    chat_id: Optional[int] = None
    max_entities: int = Field(default=8, ge=1, le=25)
    max_relations: int = Field(default=30, ge=1, le=100)


class GraphContextFact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str
    source_document_ids: list[int] = Field(default_factory=list)


class GraphContextResult(BaseModel):
    """Lenient view of the graph context response: only the fields the RAG
    flow consumes are parsed; structured entities/relations are ignored."""

    model_config = ConfigDict(extra="ignore")

    context_text: str = ""
    facts: list[GraphContextFact] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)

    @classmethod
    def empty(cls) -> "GraphContextResult":
        return cls()
