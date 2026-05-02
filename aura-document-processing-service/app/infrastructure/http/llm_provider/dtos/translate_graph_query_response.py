from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

from app.domain.constants.graph.query_intent import QueryIntent
from app.domain.dtos.graph.graph_field_limits import MAX_GRAPH_QUERY_PARAMETER_KEYS


class TranslateGraphQueryResponse(BaseModel):
    """Structured intent emitted by the LLM in response to a natural-language
    question over the knowledge graph.

    Important: the LLM never returns raw Cypher. It returns one of the
    ``QueryIntent`` values plus a ``parameters`` dictionary. The graph
    services map each intent to a parametrized Cypher template, which
    eliminates Cypher injection by construction.
    """

    intent: QueryIntent = Field(...)
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: Optional[str] = Field(default=None, max_length=2_000)

    @field_validator("parameters", mode="after")
    @classmethod
    def validate_parameters_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(v) > MAX_GRAPH_QUERY_PARAMETER_KEYS:
            raise ValueError(
                f"parameters must not contain more than "
                f"{MAX_GRAPH_QUERY_PARAMETER_KEYS} keys."
            )
        return v
