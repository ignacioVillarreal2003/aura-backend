from typing import Optional

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

_MAX_ID = 2_147_483_647
_MAX_NAME_CHARS = 255
_MAX_DESCRIPTION_CHARS = 2_000
_MAX_CATEGORY_CHARS = 100
_MAX_FRAGMENT_CONTENT_CHARS = 50_000
_MAX_FRAGMENT_SUMMARY_CHARS = 50_000
_MAX_TOPIC_CHARS = 500
_MAX_TOPICS = 100
_MAX_FRAGMENT_INDEX = 100_000
_MAX_ENTITY_KEYS = 200
_MAX_ENTITY_KEY_CHARS = 255
_MAX_ENTITY_VALUE_CHARS = 1_000


class FragmentEmbeddedDocument(BaseModel):
    """Subset of document fields returned by DPS on each fragment (fragment-query)."""

    id: int = Field(..., gt=0, le=_MAX_ID)
    name: str = Field(..., min_length=1, max_length=_MAX_NAME_CHARS)
    description: Optional[str] = Field(default=None, min_length=1, max_length=_MAX_DESCRIPTION_CHARS)
    type: Optional[str] = Field(default=None, max_length=64)
    category: Optional[str] = Field(default=None, min_length=1, max_length=_MAX_CATEGORY_CHARS)

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
    id: int = Field(..., gt=0, le=_MAX_ID)
    content: str = Field(..., min_length=1, max_length=_MAX_FRAGMENT_CONTENT_CHARS)
    fragment_index: int = Field(..., ge=0, le=_MAX_FRAGMENT_INDEX)
    summary: Optional[str] = Field(default=None, min_length=1, max_length=_MAX_FRAGMENT_SUMMARY_CHARS)
    entities: Optional[dict[str, object]] = Field(default=None)
    topics: Optional[list[str]] = Field(default=None, max_length=_MAX_TOPICS)
    document: FragmentEmbeddedDocument = Field(...)

    @computed_field
    @property
    def document_id(self) -> int:
        return self.document.id

    @field_validator("content", mode="before")
    @classmethod
    def sanitize_content(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        content = v.strip()
        if not content:
            raise ValueError("content must not be blank.")
        return content[:_MAX_FRAGMENT_CONTENT_CHARS]

    @field_validator("summary", mode="before")
    @classmethod
    def sanitize_summary(cls, v: object) -> Optional[str]:
        if not isinstance(v, str):
            return v
        summary = v.strip()
        return summary[:_MAX_FRAGMENT_SUMMARY_CHARS] if summary else None

    @field_validator("topics", mode="before")
    @classmethod
    def sanitize_topics(cls, v: object) -> Optional[list[str]]:
        if not isinstance(v, list):
            return v
        cleaned = [t.strip()[:_MAX_TOPIC_CHARS] for t in v if isinstance(t, str) and t.strip()]
        return cleaned or None

    @model_validator(mode="after")
    def validate_entities(self) -> "FragmentResponse":
        if self.entities is None:
            return self

        if len(self.entities) > _MAX_ENTITY_KEYS:
            raise ValueError(f"entities must not exceed {_MAX_ENTITY_KEYS} keys.")

        for key, value in self.entities.items():
            if not isinstance(key, str):
                raise ValueError("Each entity key must be a string.")
            if len(key) > _MAX_ENTITY_KEY_CHARS:
                raise ValueError(
                    f"Entity key '{key[:40]}...' exceeds {_MAX_ENTITY_KEY_CHARS} characters."
                )
            if isinstance(value, str) and len(value) > _MAX_ENTITY_VALUE_CHARS:
                raise ValueError(
                    f"Entity value for key '{key}' exceeds {_MAX_ENTITY_VALUE_CHARS} characters."
                )

        return self

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }
