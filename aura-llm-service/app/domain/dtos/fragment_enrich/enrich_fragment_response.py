from typing import Any
from pydantic import BaseModel, Field, model_validator

from app.domain.field_limits import (
    MAX_SUMMARY_CHARS,
    MAX_TOPICS,
    MAX_TOPIC_CHARS,
    MAX_ENTITY_KEYS,
    MAX_ENTITY_KEY_CHARS,
    MAX_ENTITY_VALUE_CHARS,
)


class EnrichFragmentResponse(BaseModel):
    summary: str = Field(..., min_length=1, max_length=MAX_SUMMARY_CHARS)
    entities: dict[str, Any] = Field(...)
    topics: list[str] = Field(..., max_length=MAX_TOPICS)

    @model_validator(mode="after")
    def validate_response(self) -> "EnrichFragmentResponse":
        if len(self.entities) > MAX_ENTITY_KEYS:
            raise ValueError(f"Entities must not exceed {MAX_ENTITY_KEYS} keys.")
        for key, value in self.entities.items():
            if len(key) > MAX_ENTITY_KEY_CHARS:
                raise ValueError(f"Entity key must not exceed {MAX_ENTITY_KEY_CHARS} characters.")
            if isinstance(value, str) and len(value) > MAX_ENTITY_VALUE_CHARS:
                raise ValueError(f"Entity value must not exceed {MAX_ENTITY_VALUE_CHARS} characters.")
        for topic in self.topics:
            if not topic or not topic.strip():
                raise ValueError("Topic must not be blank.")
            if len(topic) > MAX_TOPIC_CHARS:
                raise ValueError(f"Topic must not exceed {MAX_TOPIC_CHARS} characters.")
        return self

    model_config = {"from_attributes": True}
