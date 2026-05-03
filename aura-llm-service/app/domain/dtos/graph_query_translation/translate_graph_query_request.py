from pydantic import BaseModel, Field

from app.domain.field_limits import (
    MAX_GRAPH_ENTITY_TYPE_CHARS,
    MAX_GRAPH_ENTITY_TYPES_PER_ONTOLOGY,
    MAX_GRAPH_QUERY_QUESTION_CHARS,
    MAX_GRAPH_RELATION_TYPE_CHARS,
    MAX_GRAPH_RELATION_TYPES_PER_ONTOLOGY,
)


class GraphOntology(BaseModel):
    entity_types: list[str] = Field(
        ..., min_length=1, max_length=MAX_GRAPH_ENTITY_TYPES_PER_ONTOLOGY
    )
    relation_types: list[str] = Field(
        default_factory=list, max_length=MAX_GRAPH_RELATION_TYPES_PER_ONTOLOGY
    )


class TranslateGraphQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_GRAPH_QUERY_QUESTION_CHARS)
    ontology: GraphOntology = Field(...)

    model_config = {"frozen": True}

    @classmethod
    def _validate_lengths(cls, values: list[str], field_name: str, max_len: int) -> None:
        for v in values:
            if not v or not v.strip():
                raise ValueError(f"{field_name} entries must not be blank.")
            if len(v) > max_len:
                raise ValueError(
                    f"{field_name} entries must not exceed {max_len} characters."
                )

    def model_post_init(self, __context: object) -> None:
        self._validate_lengths(
            list(self.ontology.entity_types),
            field_name="ontology.entity_types",
            max_len=MAX_GRAPH_ENTITY_TYPE_CHARS,
        )
        self._validate_lengths(
            list(self.ontology.relation_types),
            field_name="ontology.relation_types",
            max_len=MAX_GRAPH_RELATION_TYPE_CHARS,
        )
