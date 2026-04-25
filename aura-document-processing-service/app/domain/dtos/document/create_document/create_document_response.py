from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.constants.document.document_mime_type import DocumentMimeType
from app.domain.constants.document.document_status import DocumentStatus
from app.domain.field_limits import (
    MAX_ID,
    MAX_NAME_CHARS,
    MAX_STORAGE_URL_CHARS,
    MIN_FILE_SIZE_BYTES,
)
from app.domain.types import DocumentId, UserId


class CreateDocumentResponse(BaseModel):
    id: DocumentId = Field(..., gt=0, le=MAX_ID)
    name: str = Field(..., min_length=1, max_length=MAX_NAME_CHARS)
    mime_type: DocumentMimeType = Field(...)
    status: DocumentStatus = Field(...)
    storage_url: str = Field(..., min_length=1, max_length=MAX_STORAGE_URL_CHARS)
    file_size_bytes: int = Field(..., ge=MIN_FILE_SIZE_BYTES)
    processing_started_at: datetime = Field(...)
    created_by: UserId = Field(..., gt=0, le=MAX_ID)
    created_at: datetime = Field(...)

    @field_validator("name", mode="after")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name must not be blank.")
        return s

    @model_validator(mode="after")
    def validate_timestamps(self) -> "CreateDocumentResponse":
        if self.processing_started_at > self.created_at:
            raise ValueError("processing_started_at cannot be after created_at.")
        return self

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }
