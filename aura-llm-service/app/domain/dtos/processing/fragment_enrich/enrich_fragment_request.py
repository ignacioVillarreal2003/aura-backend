from pydantic import BaseModel, Field, model_validator

from app.domain.field_limits import MAX_CONTENT_CHARS


class EnrichFragmentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)

    @model_validator(mode="after")
    def validate_request(self) -> "EnrichFragmentRequest":
        content = self.content.strip()
        if not content:
            raise ValueError("Content must not be blank.")
        if content != self.content:
            return self.model_copy(update={"content": content})
        return self

    model_config = {"frozen": True}
