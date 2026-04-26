import json
from typing import Any
from pydantic import BaseModel, Field, field_validator

from app.domain.field_limits import (
    MAX_SUMMARY_CHARS,
    MAX_TOPICS,
    MAX_TOPIC_CHARS,
    MAX_ENTITY_KEYS,
    MAX_ENTITY_KEY_CHARS,
    MAX_ENTITY_VALUE_CHARS,
)


class EnrichFragmentResponse(BaseModel):
    summary: str = Field(..., max_length=MAX_SUMMARY_CHARS)
    entities: dict[str, Any] = Field(...)
    topics: list[str] = Field(..., max_length=MAX_TOPICS)

    @field_validator("topics", mode="after")
    @classmethod
    def validate_topic_lengths(cls, v: list[str]) -> list[str]:
        for topic in v:
            if len(topic) > MAX_TOPIC_CHARS:
                raise ValueError(
                    f"Each topic must not exceed {MAX_TOPIC_CHARS} characters."
                )
        return v

    @field_validator("entities", mode="after")
    @classmethod
    def validate_entities_shape(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(v) > MAX_ENTITY_KEYS:
            raise ValueError(
                f"The entities map must not exceed {MAX_ENTITY_KEYS} keys."
            )
        for key, value in v.items():
            if len(key) > MAX_ENTITY_KEY_CHARS:
                raise ValueError(
                    f"Each entity key must not exceed {MAX_ENTITY_KEY_CHARS} characters."
                )
            serialized = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            if len(serialized) > MAX_ENTITY_VALUE_CHARS:
                raise ValueError(
                    f"Each entity value must not exceed {MAX_ENTITY_VALUE_CHARS} characters when serialized."
                )
        return v
