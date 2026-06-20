from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.field_limits import (
    MAX_CATEGORY_CHARS,
    MAX_DESCRIPTION_CHARS,
    MAX_ENTITY_KEY_CHARS,
    MAX_ENTITY_VALUE_CHARS,
    MAX_ENTITY_KEYS,
    MAX_FRAGMENT_CONTENT_CHARS,
    MAX_FRAGMENT_INDEX,
    MAX_FRAGMENT_SUMMARY_CHARS,
    MAX_ID,
    MAX_NAME_CHARS,
    MAX_TOPIC_CHARS,
    MAX_TOPICS,
)
from app.domain.types import DocumentId, FragmentId


class _Document(BaseModel):
    id: DocumentId = Field(..., gt=0, le=MAX_ID)
    name: str = Field(..., min_length=1, max_length=MAX_NAME_CHARS)
    description: str | None = Field(default=None, min_length=1, max_length=MAX_DESCRIPTION_CHARS)
    type: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, min_length=1, max_length=MAX_CATEGORY_CHARS)

    @field_validator("name", mode="after")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name must not be blank.")
        return s

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        stripped = v.strip()
        return stripped or None

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        stripped = v.strip()
        return stripped or None

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }


class FragmentResponse(BaseModel):
    id: FragmentId = Field(..., gt=0, le=MAX_ID)
    content: str = Field(..., min_length=1, max_length=MAX_FRAGMENT_CONTENT_CHARS)
    fragment_index: int = Field(..., ge=0, le=MAX_FRAGMENT_INDEX)
    summary: str | None = Field(default=None, min_length=1, max_length=MAX_FRAGMENT_SUMMARY_CHARS)
    entities: dict[str, object] | None = Field(default=None)
    topics: list[str] | None = Field(default=None, max_length=MAX_TOPICS)
    enrichment_status: str = Field(default="pending", min_length=1, max_length=32)

    page_number: int | None = Field(default=None, ge=1)
    section_path: str | None = Field(default=None)
    heading: str | None = Field(default=None)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    bbox: dict[str, Any] | None = Field(default=None)

    document: _Document = Field(...)

    @field_validator("content", mode="before")
    @classmethod
    def sanitize_content(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        content = v.strip()
        if not content:
            raise ValueError("content must not be blank.")
        return content[:MAX_FRAGMENT_CONTENT_CHARS]

    @field_validator("summary", mode="before")
    @classmethod
    def sanitize_summary(cls, v: object) -> Any:
        if not isinstance(v, str):
            return v
        summary = v.strip()
        return summary[:MAX_FRAGMENT_SUMMARY_CHARS] if summary else None

    @field_validator("topics", mode="before")
    @classmethod
    def sanitize_topics(cls, v: object) -> Any:
        if not isinstance(v, list):
            return v
        cleaned = [t.strip()[:MAX_TOPIC_CHARS] for t in v if isinstance(t, str) and t.strip()]
        return cleaned or None

    @model_validator(mode="after")
    def validate_entities(self) -> "FragmentResponse":
        if self.entities is None:
            return self

        if len(self.entities) > MAX_ENTITY_KEYS:
            raise ValueError(f"entities must not exceed {MAX_ENTITY_KEYS} keys.")

        for key, value in self.entities.items():
            if not isinstance(key, str):
                raise ValueError("Each entity key must be a string.")
            if len(key) > MAX_ENTITY_KEY_CHARS:
                raise ValueError(
                    f"Entity key '{key[:40]}...' exceeds {MAX_ENTITY_KEY_CHARS} characters."
                )
            if isinstance(value, str) and len(value) > MAX_ENTITY_VALUE_CHARS:
                raise ValueError(
                    f"Entity value for key '{key}' exceeds {MAX_ENTITY_VALUE_CHARS} characters."
                )

        return self

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }
