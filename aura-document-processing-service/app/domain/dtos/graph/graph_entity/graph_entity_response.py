from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.domain.constants.graph.entity_type import EntityType
from app.domain.field_limits import MAX_ENTITY_NAME_CHARS
from app.domain.dtos.graph.graph_field_limits import (
    MAX_ENTITY_ALIASES,
    MAX_ENTITY_DESCRIPTION_CHARS,
)


class GraphEntityResponse(BaseModel):
    canonical_name: str = Field(..., min_length=1, max_length=MAX_ENTITY_NAME_CHARS)
    display_name: str = Field(..., min_length=1, max_length=MAX_ENTITY_NAME_CHARS)
    type: EntityType = Field(...)
    aliases: list[str] = Field(default_factory=list, max_length=MAX_ENTITY_ALIASES)
    description: Optional[str] = Field(
        default=None, max_length=MAX_ENTITY_DESCRIPTION_CHARS
    )
    source_document_ids: list[int] = Field(default_factory=list)
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)

    model_config = {"from_attributes": True}
