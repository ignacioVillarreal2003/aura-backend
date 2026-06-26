from typing import Optional
from pydantic import BaseModel, Field, field_validator

from app.domain.field_limits import (
    MAX_CONTENT_CHARS,
    MAX_ENTITIES_PER_FRAGMENT,
    MAX_GRAPH_ENTITY_TYPE_CHARS,
    MAX_GRAPH_ENTITY_TYPES_PER_ONTOLOGY,
    MAX_GRAPH_RELATION_TYPE_CHARS,
    MAX_GRAPH_RELATION_TYPES_PER_ONTOLOGY,
    MAX_ID,
    MAX_RELATIONS_PER_FRAGMENT,
)


class ExtractEntitiesRelationsRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)
    document_id: int = Field(..., ge=1, le=MAX_ID)
    fragment_id: int = Field(..., ge=1, le=MAX_ID)
    allowed_entity_types: list[str] = Field(
        ...,
        min_length=1,
        max_length=MAX_GRAPH_ENTITY_TYPES_PER_ONTOLOGY,
    )
    allowed_relation_types: Optional[list[str]] = Field(
        default=None,
        max_length=MAX_GRAPH_RELATION_TYPES_PER_ONTOLOGY,
    )
    max_entities: int = Field(
        default=MAX_ENTITIES_PER_FRAGMENT,
        ge=1,
        le=MAX_ENTITIES_PER_FRAGMENT,
    )
    max_relations: int = Field(
        default=MAX_RELATIONS_PER_FRAGMENT,
        ge=0,
        le=MAX_RELATIONS_PER_FRAGMENT,
    )

    model_config = {"frozen": True, "extra": "forbid"}

    @staticmethod
    def _validate_type_lengths(
            values: list[str],
            *,
            field_name: str,
            max_len: int,
    ) -> list[str]:
        for v in values:
            if not v or not v.strip():
                raise ValueError(f"{field_name} entries must not be blank.")
            if len(v) > max_len:
                raise ValueError(
                    f"{field_name} entries must not exceed {max_len} characters."
                )
        return values

    @field_validator("allowed_entity_types")
    @classmethod
    def _validate_entity_types(cls, values: list[str]) -> list[str]:
        return cls._validate_type_lengths(
            values,
            field_name="allowed_entity_types",
            max_len=MAX_GRAPH_ENTITY_TYPE_CHARS,
        )

    @field_validator("allowed_relation_types")
    @classmethod
    def _validate_relation_types(cls, values: Optional[list[str]]) -> Optional[list[str]]:
        if values is None:
            return None
        return cls._validate_type_lengths(
            values,
            field_name="allowed_relation_types",
            max_len=MAX_GRAPH_RELATION_TYPE_CHARS,
        )
