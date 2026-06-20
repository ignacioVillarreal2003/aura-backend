from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.field_limits import (
    MAX_CATEGORY_CHARS,
    MAX_DESCRIPTION_CHARS,
    MAX_NAME_CHARS,
)


class UpdateDocumentRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=MAX_NAME_CHARS)
    description: Optional[str] = Field(default=None, max_length=MAX_DESCRIPTION_CHARS)
    category: Optional[str] = Field(default=None, min_length=1, max_length=MAX_CATEGORY_CHARS)

    model_config = {"extra": "forbid"}

    @field_validator("name", "category", mode="after")
    @classmethod
    def not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        s = v.strip()
        if not s:
            raise ValueError("The value must not be blank.")
        return s

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        stripped = v.strip()
        return stripped or None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateDocumentRequest":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided to update the document.")
        return self
