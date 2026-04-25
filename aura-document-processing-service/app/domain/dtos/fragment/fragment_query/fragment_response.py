from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.field_limits import (
    MAX_CONTENT_CHARS,
    MAX_ENTITY_KEY_CHARS,
    MAX_ENTITY_KEYS,
    MAX_ENTITY_VALUE_CHARS,
    MAX_FRAGMENT_INDEX,
    MAX_ID,
    MAX_SUMMARY_CHARS,
    MAX_TOPIC_CHARS,
    MAX_TOPICS,
)
from app.domain.types import UserId, DocumentId, FragmentId


class FragmentResponse(BaseModel):
    id: FragmentId = Field(..., gt=0, le=MAX_ID)
    document_id: DocumentId = Field(..., gt=0, le=MAX_ID)
    content: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)
    fragment_index: int = Field(..., ge=0, le=MAX_FRAGMENT_INDEX)
    summary: Optional[str] = Field(default=None, min_length=1, max_length=MAX_SUMMARY_CHARS)
    entities: Optional[dict] = Field(default=None)
    topics: Optional[list[str]] = Field(default=None, max_length=MAX_TOPICS)
    created_by: UserId = Field(..., gt=0, le=MAX_ID)
    created_at: datetime = Field(...)
    updated_by: Optional[UserId] = Field(default=None, gt=0, le=MAX_ID)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[UserId] = Field(default=None, gt=0, le=MAX_ID)
    deleted_at: Optional[datetime] = Field(default=None)

    @field_validator("content", mode="before")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        content = v.strip()
        if not content:
            raise ValueError("content must not be blank.")
        return content[:MAX_CONTENT_CHARS]

    @field_validator("summary", mode="before")
    @classmethod
    def sanitize_summary(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        summary = v.strip()
        if not summary:
            return None
        return summary[:MAX_SUMMARY_CHARS]

    @field_validator("topics", mode="before")
    @classmethod
    def sanitize_topics(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return None
        cleaned = [t.strip()[:MAX_TOPIC_CHARS] for t in v if t and t.strip()]
        return cleaned or None

    @model_validator(mode="after")
    def validate_entities_and_pairs(self) -> "FragmentResponse":
        if self.entities is not None:
            if len(self.entities) > MAX_ENTITY_KEYS:
                raise ValueError(f"entities must not exceed {MAX_ENTITY_KEYS} keys.")
            for key, value in self.entities.items():
                if not isinstance(key, str) or len(key) > MAX_ENTITY_KEY_CHARS:
                    raise ValueError(
                        f"Each entity key must be a string of at most {MAX_ENTITY_KEY_CHARS} characters."
                    )
                if isinstance(value, str) and len(value) > MAX_ENTITY_VALUE_CHARS:
                    raise ValueError(
                        f"Entity value for key '{key}' exceeds {MAX_ENTITY_VALUE_CHARS} characters."
                    )

        if self.updated_at and self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be before created_at.")
        if self.deleted_at and self.deleted_at < self.created_at:
            raise ValueError("deleted_at cannot be before created_at.")
        if (self.updated_at is None) != (self.updated_by is None):
            raise ValueError("updated_at and updated_by must both be set or both be absent.")
        if (self.deleted_at is None) != (self.deleted_by is None):
            raise ValueError("deleted_at and deleted_by must both be set or both be absent.")

        return self

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }
