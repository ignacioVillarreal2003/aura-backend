from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

from app.domain.constants.graph.entity_type import EntityType
from app.domain.field_limits import (
    MAX_ENTITY_ALIAS_CHARS,
    MAX_ENTITY_ALIASES,
    MAX_ENTITY_DESCRIPTION_CHARS,
    MAX_ENTITY_NAME_CHARS,
)


class ExtractedEntity(BaseModel):
    name: str = Field(..., min_length=1, max_length=MAX_ENTITY_NAME_CHARS)
    type: EntityType = Field(...)
    aliases: list[str] = Field(default_factory=list, max_length=MAX_ENTITY_ALIASES)
    description: Optional[str] = Field(
        default=None,
        max_length=MAX_ENTITY_DESCRIPTION_CHARS,
    )

    @field_validator("type", mode="before")
    @classmethod
    def normalize_entity_type(cls, v: Any) -> str:
        if isinstance(v, EntityType):
            return v.value
        return EntityType.parse(str(v)).value

    @field_validator("name", mode="after")
    @classmethod
    def trim_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("entity name must not be blank.")
        return v

    @field_validator("aliases", mode="after")
    @classmethod
    def validate_aliases(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        for alias in v:
            stripped = (alias or "").strip()
            if not stripped:
                continue
            if len(stripped) > MAX_ENTITY_ALIAS_CHARS:
                raise ValueError(
                    f"each alias must not exceed {MAX_ENTITY_ALIAS_CHARS} characters."
                )
            cleaned.append(stripped)
        return cleaned
