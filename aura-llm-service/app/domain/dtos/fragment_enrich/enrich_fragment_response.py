from typing import Any

from pydantic import BaseModel, Field


class EnrichFragmentResponse(BaseModel):
    summary: str = Field(...)
    entities: dict[str, Any] = Field(...)
    topics: list[str] = Field(...)
