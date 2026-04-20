from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator

MAX_CONTENT_CHARS = 50_000


class FragmentResponse(BaseModel):
    id: int = Field(..., gt=0)
    document_id: int = Field(..., gt=0)
    content: str = Field(..., min_length=1)
    fragment_index: int = Field(..., ge=0)
    summary: Optional[str] = Field(default=None, min_length=1)
    entities: Optional[dict] = None
    topics: Optional[list[str]] = None
    created_by: int = Field(..., gt=0)
    created_at: datetime
    updated_by: Optional[int] = Field(default=None, gt=0)
    updated_at: Optional[datetime] = None
    deleted_by: Optional[int] = Field(default=None, gt=0)
    deleted_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

    @model_validator(mode="after")
    def validate_and_sanitize_fields(self) -> "FragmentResponse":
        content = self.content.strip()
        if not content:
            raise ValueError("content must not be empty.")
        self.content = content[:MAX_CONTENT_CHARS]

        if self.summary is not None:
            self.summary = self.summary.strip() or None

        if self.topics is not None:
            cleaned_topics = [topic.strip() for topic in self.topics if topic and topic.strip()]
            self.topics = cleaned_topics or None

        return self
