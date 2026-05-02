from pydantic import BaseModel, Field

from app.domain.dtos.graph.graph_field_limits import (
    MAX_ENTITY_TYPE_CHARS,
    MAX_QUERY_QUESTION_CHARS,
    MAX_RELATION_TYPE_CHARS,
)


class GraphOntology(BaseModel):
    """Ontology snapshot sent to the LLM so it can ground the question
    on the entity and relation types that exist in the graph.

    The LLM never receives raw Cypher; it returns a structured intent
    plus parameters validated against this ontology.
    """

    entity_types: list[str] = Field(..., min_length=1, max_length=64)
    relation_types: list[str] = Field(default_factory=list, max_length=128)


class TranslateGraphQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUERY_QUESTION_CHARS)
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
            max_len=MAX_ENTITY_TYPE_CHARS,
        )
        self._validate_lengths(
            list(self.ontology.relation_types),
            field_name="ontology.relation_types",
            max_len=MAX_RELATION_TYPE_CHARS,
        )
