from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class GraphContextProviderRequest(BaseModel):
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
    model_config = ConfigDict(extra="ignore")

    context_text: str = ""
    facts: list[GraphContextFact] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)

    @classmethod
    def empty(cls) -> "GraphContextResult":
        return cls()


class GraphQueryProviderRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: str
    max_results: int = Field(default=20, ge=1, le=100)
    chat_id: Optional[int] = None


class _GraphQueryEntity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    display_name: str
    type: str
    description: Optional[str] = None


class _GraphQueryEndpoint(BaseModel):
    model_config = ConfigDict(extra="ignore")

    display_name: str
    type: str


class _GraphQueryRelation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str
    source: _GraphQueryEndpoint
    target: _GraphQueryEndpoint


class GraphQueryProviderResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entities: list[_GraphQueryEntity] = Field(default_factory=list)
    relations: list[_GraphQueryRelation] = Field(default_factory=list)
    explanation: Optional[str] = None


class GraphQueryResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    context_text: str = ""
    entities_count: int = 0
    relations_count: int = 0

    @classmethod
    def empty(cls) -> "GraphQueryResult":
        return cls()
