from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

from app.domain.constants.graph.query_intent import QueryIntent
from app.domain.dtos.graph.graph_field_limits import (
    MAX_GRAPH_QUERY_PARAMETER_KEYS,
    MAX_GRAPH_QUERY_REASONING_CHARS,
)


class TranslateGraphQueryResponse(BaseModel):
    intent: QueryIntent = Field(...)
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: Optional[str] = Field(default=None, max_length=MAX_GRAPH_QUERY_REASONING_CHARS)

    @field_validator("parameters", mode="after")
    @classmethod
    def validate_parameters_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(v) > MAX_GRAPH_QUERY_PARAMETER_KEYS:
            raise ValueError(
                f"parameters must not contain more than "
                f"{MAX_GRAPH_QUERY_PARAMETER_KEYS} keys."
            )
        return v
