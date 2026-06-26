from pydantic import BaseModel, Field, field_validator

from app.domain.field_limits import MAX_NAME_CHARS


class UpdateDocumentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=MAX_NAME_CHARS)

    model_config = {"extra": "forbid"}

    @field_validator("name", mode="after")
    @classmethod
    def not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("The value must not be blank.")
        return s
