from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

MAX_ID = 2_147_483_647
MAX_CONTENT_CHARS = 50_000
MAX_SUMMARY_CHARS = 10_000
MAX_TOPIC_CHARS = 500
MAX_TOPICS = 100
MAX_FRAGMENT_INDEX = 100_000
MAX_ENTITY_KEYS = 200
MAX_ENTITY_KEY_CHARS = 255
MAX_ENTITY_VALUE_CHARS = 1_000


class FragmentResponse(BaseModel):
    id: int = Field(..., gt=0, le=MAX_ID)
    document_id: int = Field(..., gt=0, le=MAX_ID)
    content: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)
    fragment_index: int = Field(..., ge=0, le=MAX_FRAGMENT_INDEX)
    summary: Optional[str] = Field(default=None, min_length=1, max_length=MAX_SUMMARY_CHARS)
    entities: Optional[dict] = Field(default=None)
    topics: Optional[list[str]] = Field(default=None, max_length=MAX_TOPICS)
    created_by: int = Field(..., gt=0, le=MAX_ID)
    created_at: datetime = Field(...)
    updated_by: Optional[int] = Field(default=None, gt=0, le=MAX_ID)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[int] = Field(default=None, gt=0, le=MAX_ID)
    deleted_at: Optional[datetime] = Field(default=None)

    model_config = {
        "from_attributes": True
    }

    @model_validator(mode="after")
    def validate_and_sanitize_fields(self) -> "FragmentResponse":
        content = self.content.strip()
        if not content:
            raise ValueError("content must not be blank.")
        self.content = content[:MAX_CONTENT_CHARS]

        if self.summary is not None:
            summary = self.summary.strip()
            self.summary = summary[:MAX_SUMMARY_CHARS] if summary else None

        if self.topics is not None:
            cleaned = [t.strip()[:MAX_TOPIC_CHARS] for t in self.topics if t and t.strip()]
            self.topics = cleaned or None

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
