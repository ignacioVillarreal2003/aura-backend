from pydantic import BaseModel, Field, field_validator

from app.domain.field_limits import (
    MAX_GRAPH_ENTITY_TYPE_CHARS,
    MAX_GRAPH_ENTITY_TYPES_PER_ONTOLOGY,
    MAX_GRAPH_QUERY_QUESTION_CHARS,
    MAX_GRAPH_RELATION_TYPE_CHARS,
    MAX_GRAPH_RELATION_TYPES_PER_ONTOLOGY,
)


def _validate_type_lengths(values: list[str], *, field_name: str, max_len: int) -> list[str]:
    for v in values:
        if not v or not v.strip():
            raise ValueError(f"{field_name} entries must not be blank.")
        if len(v) > max_len:
            raise ValueError(
                f"{field_name} entries must not exceed {max_len} characters."
            )
    return values


class GraphOntology(BaseModel):
    entity_types: list[str] = Field(
        ..., min_length=1, max_length=MAX_GRAPH_ENTITY_TYPES_PER_ONTOLOGY
    )
    relation_types: list[str] = Field(
        default_factory=list, max_length=MAX_GRAPH_RELATION_TYPES_PER_ONTOLOGY
    )

    model_config = {"frozen": True, "extra": "forbid"}

    @field_validator("entity_types")
    @classmethod
    def _validate_entity_types(cls, values: list[str]) -> list[str]:
        return _validate_type_lengths(
            values, field_name="entity_types", max_len=MAX_GRAPH_ENTITY_TYPE_CHARS
        )

    @field_validator("relation_types")
    @classmethod
    def _validate_relation_types(cls, values: list[str]) -> list[str]:
        return _validate_type_lengths(
            values, field_name="relation_types", max_len=MAX_GRAPH_RELATION_TYPE_CHARS
        )


class TranslateGraphQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_GRAPH_QUERY_QUESTION_CHARS)
    ontology: GraphOntology = Field(...)

    model_config = {"frozen": True, "extra": "forbid"}
