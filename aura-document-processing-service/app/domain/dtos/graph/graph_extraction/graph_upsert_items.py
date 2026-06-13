from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.domain.constants.graph.entity_type import EntityType


class EntityUpsertItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    canonical_name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    entity_type: EntityType
    aliases: tuple[str, ...] = ()
    description: Optional[str] = None


class RelationUpsertItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_canonical_name: str = Field(min_length=1)
    source_type: EntityType
    target_canonical_name: str = Field(min_length=1)
    target_type: EntityType
    relation_type: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
