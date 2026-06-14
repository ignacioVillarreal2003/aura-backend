from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.dtos.graph.graph_field_limits import MAX_QUERY_QUESTION_CHARS
from app.domain.field_limits import MAX_ENTITY_NAME_CHARS, MAX_ID
from app.domain.types import ChatId

MAX_CONTEXT_TERMS = 15
MAX_CONTEXT_ENTITIES = 25
MAX_CONTEXT_RELATIONS = 100


class GraphContextRequest(BaseModel):
    question: Optional[str] = Field(default=None, max_length=MAX_QUERY_QUESTION_CHARS)
    terms: list[str] = Field(default_factory=list, max_length=MAX_CONTEXT_TERMS)
    chat_id: Optional[ChatId] = Field(default=None, gt=0, le=MAX_ID)
    max_entities: int = Field(default=8, ge=1, le=MAX_CONTEXT_ENTITIES)
    max_relations: int = Field(default=30, ge=1, le=MAX_CONTEXT_RELATIONS)

    model_config = {"frozen": True}

    @field_validator("terms", mode="after")
    @classmethod
    def clean_terms(cls, v: list[str]) -> list[str]:
        return [t.strip()[:MAX_ENTITY_NAME_CHARS] for t in v if t and t.strip()]

    @field_validator("question", mode="after")
    @classmethod
    def clean_question(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip() or None

    @model_validator(mode="after")
    def validate_inputs(self) -> "GraphContextRequest":
        if not self.terms and not self.question:
            raise ValueError("Either 'terms' or 'question' must be provided.")
        return self
