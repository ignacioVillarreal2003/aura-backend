from pydantic import BaseModel, Field, field_validator

from app.domain.dtos.processing.graph_extraction.extracted_entity import ExtractedEntity
from app.domain.dtos.processing.graph_extraction.extracted_relation import ExtractedRelation
from app.domain.field_limits import (
    MAX_ENTITIES_PER_FRAGMENT,
    MAX_RELATIONS_PER_FRAGMENT,
)


class ExtractEntitiesRelationsResponse(BaseModel):
    entities: list[ExtractedEntity] = Field(
        default_factory=list,
        max_length=MAX_ENTITIES_PER_FRAGMENT,
    )
    relations: list[ExtractedRelation] = Field(
        default_factory=list,
        max_length=MAX_RELATIONS_PER_FRAGMENT,
    )

    @field_validator("relations", mode="after")
    @classmethod
    def filter_self_loop_relations(
            cls, v: list[ExtractedRelation]
    ) -> list[ExtractedRelation]:
        return [
            r for r in v
            if not (
                r.source.name.strip().lower() == r.target.name.strip().lower()
                and r.source.type == r.target.type
            )
        ]

    model_config = {"from_attributes": True}
