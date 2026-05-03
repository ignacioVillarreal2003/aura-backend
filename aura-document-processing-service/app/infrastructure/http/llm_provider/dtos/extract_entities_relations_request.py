from typing import Optional
from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_CONTENT_CHARS, MAX_ID
from app.domain.dtos.graph.graph_field_limits import (
    MAX_ENTITIES_PER_FRAGMENT,
    MAX_ENTITY_TYPE_CHARS,
    MAX_ONTOLOGY_ENTITY_TYPES,
    MAX_ONTOLOGY_RELATION_TYPES,
    MAX_RELATION_TYPE_CHARS,
    MAX_RELATIONS_PER_FRAGMENT,
)


class ExtractEntitiesRelationsRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)
    document_id: int = Field(..., ge=1, le=MAX_ID)
    fragment_id: int = Field(..., ge=1, le=MAX_ID)
    allowed_entity_types: list[str] = Field(..., min_length=1, max_length=MAX_ONTOLOGY_ENTITY_TYPES)
    allowed_relation_types: Optional[list[str]] = Field(default=None, max_length=MAX_ONTOLOGY_RELATION_TYPES)
    max_entities: int = Field(default=MAX_ENTITIES_PER_FRAGMENT, ge=1, le=MAX_ENTITIES_PER_FRAGMENT)
    max_relations: int = Field(default=MAX_RELATIONS_PER_FRAGMENT, ge=0, le=MAX_RELATIONS_PER_FRAGMENT)

    model_config = {"frozen": True}

    @classmethod
    def _validate_type_lengths(
            cls,
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

    def model_post_init(self, __context: object) -> None:
        self._validate_type_lengths(
            list(self.allowed_entity_types),
            field_name="allowed_entity_types",
            max_len=MAX_ENTITY_TYPE_CHARS,
        )
        if self.allowed_relation_types is not None:
            self._validate_type_lengths(
                list(self.allowed_relation_types),
                field_name="allowed_relation_types",
                max_len=MAX_RELATION_TYPE_CHARS,
            )
