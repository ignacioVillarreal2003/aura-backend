from pydantic import BaseModel, Field, field_validator

from app.domain.field_limits import MAX_CONTENT_CHARS
from app.domain.validation import stripped_non_blank


class EnrichFragmentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)

    @field_validator("content")
    @classmethod
    def _strip_content(cls, value: str) -> str:
        return stripped_non_blank(value, "Content must not be blank.")

    model_config = {"frozen": True}
