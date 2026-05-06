from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.field_limits import (
    MAX_CATEGORY_CHARS,
    MAX_DESCRIPTION_CHARS,
    MAX_ID,
)

_MAX_NAME_CHARS = 255
_MAX_PROCESSOR_TYPE_CHARS = 100
_MAX_SPLIT_SIZE = 10_000
_MAX_SPLIT_OVERLAP = 5_000
_MAX_STORAGE_URL_CHARS = 2_000
_MIN_FILE_SIZE_BYTES = 1


class DocumentResponse(BaseModel):
    id: int = Field(..., gt=0, le=MAX_ID)
    chat_id: Optional[int] = Field(default=None, gt=0, le=MAX_ID)
    name: str = Field(..., min_length=1, max_length=_MAX_NAME_CHARS)
    description: Optional[str] = Field(default=None, min_length=1, max_length=MAX_DESCRIPTION_CHARS)
    mime_type: str = Field(...)
    status: str = Field(...)
    storage_url: str = Field(..., min_length=1, max_length=_MAX_STORAGE_URL_CHARS)
    file_size_bytes: int = Field(..., ge=_MIN_FILE_SIZE_BYTES)
    type: Optional[str] = Field(default=None, max_length=64)
    category: Optional[str] = Field(default=None, min_length=1, max_length=MAX_CATEGORY_CHARS)
    text_cleaner_type: Optional[str] = Field(default=None, min_length=1, max_length=_MAX_PROCESSOR_TYPE_CHARS)
    text_splitter_type: Optional[str] = Field(default=None, min_length=1, max_length=_MAX_PROCESSOR_TYPE_CHARS)
    embedder_type: Optional[str] = Field(default=None, min_length=1, max_length=_MAX_PROCESSOR_TYPE_CHARS)
    split_size: Optional[int] = Field(default=None, ge=1, le=_MAX_SPLIT_SIZE)
    split_overlap: Optional[int] = Field(default=None, ge=0, le=_MAX_SPLIT_OVERLAP)
    processing_started_at: Optional[datetime] = Field(default=None)
    processing_finished_at: Optional[datetime] = Field(default=None)
    created_by: int = Field(..., gt=0, le=MAX_ID)
    created_at: datetime = Field(...)
    updated_by: Optional[int] = Field(default=None, gt=0, le=MAX_ID)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[int] = Field(default=None, gt=0, le=MAX_ID)
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
        if self.split_size is not None and self.split_overlap is not None:
            if self.split_overlap >= self.split_size:
                raise ValueError("split_overlap must be less than split_size.")

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
