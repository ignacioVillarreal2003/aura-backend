from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.field_limits import (
    MAX_CATEGORY_CHARS,
    MAX_DESCRIPTION_CHARS,
    MAX_ID,
    MAX_NAME_CHARS,
    MIN_FILE_SIZE_BYTES,
)
from app.domain.types import UserId, DocumentId, ChatId


class DocumentResponse(BaseModel):
    id: DocumentId = Field(..., gt=0, le=MAX_ID)
    chat_id: Optional[ChatId] = Field(default=None, gt=0, le=MAX_ID)
    name: str = Field(..., min_length=1, max_length=MAX_NAME_CHARS)
    description: Optional[str] = Field(default=None, min_length=1, max_length=MAX_DESCRIPTION_CHARS)
    mime_type: str = Field(..., min_length=1, max_length=64)
    status: str = Field(..., min_length=1, max_length=64)
    file_size_bytes: int = Field(..., ge=MIN_FILE_SIZE_BYTES)
    type: Optional[str] = Field(default=None, max_length=64)
    category: Optional[str] = Field(default=None, min_length=1, max_length=MAX_CATEGORY_CHARS)
    enrichment_status: str = Field(default="pending", min_length=1, max_length=32)
    graph_status: str = Field(default="pending", min_length=1, max_length=32)
    processing_started_at: Optional[datetime] = Field(default=None)
    processing_finished_at: Optional[datetime] = Field(default=None)
    created_by: UserId = Field(..., gt=0, le=MAX_ID)
    created_at: datetime = Field(...)
    updated_by: Optional[UserId] = Field(default=None, gt=0, le=MAX_ID)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[UserId] = Field(default=None, gt=0, le=MAX_ID)
    deleted_at: Optional[datetime] = Field(default=None)

    @field_validator("name", mode="after")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name must not be blank.")
        return s

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        stripped = v.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_invariants(self) -> "DocumentResponse":
        if self.processing_started_at and self.processing_finished_at:
            if self.processing_finished_at < self.processing_started_at:
                raise ValueError("processing_finished_at cannot be before processing_started_at.")

        if self.updated_at and self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be before created_at.")

        if self.deleted_at and self.deleted_at < self.created_at:
            raise ValueError("deleted_at cannot be before created_at.")

        if (self.deleted_at is None) != (self.deleted_by is None):
            raise ValueError("deleted_at and deleted_by must both be set or both be absent.")

        if (self.updated_at is None) != (self.updated_by is None):
            raise ValueError("updated_at and updated_by must both be set or both be absent.")

        return self

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }
