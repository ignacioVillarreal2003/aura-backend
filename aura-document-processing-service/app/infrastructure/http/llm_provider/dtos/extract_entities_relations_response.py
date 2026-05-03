from pydantic import BaseModel, Field, field_validator

from app.domain.dtos.graph.graph_extraction.extracted_entity import ExtractedEntity
from app.domain.dtos.graph.graph_extraction.extracted_relation import ExtractedRelation
from app.domain.dtos.graph.graph_field_limits import (
    MAX_ENTITIES_PER_FRAGMENT,
    MAX_RELATIONS_PER_FRAGMENT,
)


class ExtractEntitiesRelationsResponse(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list, max_length=MAX_ENTITIES_PER_FRAGMENT)
    relations: list[ExtractedRelation] = Field(
        default_factory=list, max_length=MAX_RELATIONS_PER_FRAGMENT
    )

    @field_validator("relations", mode="after")
    @classmethod
    def validate_relation_endpoints(
            cls, v: list[ExtractedRelation]
    ) -> list[ExtractedRelation]:
        for relation in v:
            if (
                    relation.source.name.strip().lower() == relation.target.name.strip().lower()
                    and relation.source.type == relation.target.type
            ):
                raise ValueError("relation endpoints must be different entities.")
        return v
