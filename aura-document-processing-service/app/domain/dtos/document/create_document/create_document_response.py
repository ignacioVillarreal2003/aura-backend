from pydantic import BaseModel, Field, field_validator

from app.domain.field_limits import (
    MAX_ID,
    MAX_NAME_CHARS,
    MIN_FILE_SIZE_BYTES,
)
from app.domain.types import DocumentId


class CreateDocumentResponse(BaseModel):
    id: DocumentId = Field(..., gt=0, le=MAX_ID)
    name: str = Field(..., min_length=1, max_length=MAX_NAME_CHARS)
    mime_type: str = Field(..., min_length=1, max_length=64)
    status: str = Field(..., min_length=1, max_length=64)
    file_size_bytes: int = Field(..., ge=MIN_FILE_SIZE_BYTES)

    @field_validator("name", mode="after")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name must not be blank.")
        return s

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }
