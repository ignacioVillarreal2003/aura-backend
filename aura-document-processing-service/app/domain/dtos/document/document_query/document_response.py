from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator

from app.domain.constants.document.document_status import DocumentStatus
from app.domain.constants.document.document_mime_type import DocumentMimeType
from app.domain.constants.document.document_type import DocumentType

MAX_ID = 2_147_483_647
MAX_NAME_CHARS = 255
MAX_DESCRIPTION_CHARS = 2_000
MAX_STORAGE_URL_CHARS = 1_024
MIN_FILE_SIZE_BYTES = 1
MAX_CATEGORY_CHARS = 100
MAX_PROCESSOR_TYPE_CHARS = 100
MAX_SPLIT_SIZE = 100_000
MAX_SPLIT_OVERLAP = 99_999


class DocumentResponse(BaseModel):
    id: int = Field(..., gt=0, le=MAX_ID)
    chat_id: Optional[int] = Field(default=None, gt=0, le=MAX_ID)
    name: str = Field(..., min_length=1, max_length=MAX_NAME_CHARS)
    description: Optional[str] = Field(default=None, min_length=1, max_length=MAX_DESCRIPTION_CHARS)
    mime_type: DocumentMimeType = Field(...)
    status: DocumentStatus = Field(...)
    storage_url: str = Field(..., min_length=1, max_length=MAX_STORAGE_URL_CHARS)
    file_size_bytes: int = Field(..., ge=MIN_FILE_SIZE_BYTES)
    type: Optional[DocumentType] = Field(default=None)
    category: Optional[str] = Field(default=None, min_length=1, max_length=MAX_CATEGORY_CHARS)
    text_cleaner_type: Optional[str] = Field(default=None, min_length=1, max_length=MAX_PROCESSOR_TYPE_CHARS)
    text_splitter_type: Optional[str] = Field(default=None, min_length=1, max_length=MAX_PROCESSOR_TYPE_CHARS)
    embedder_type: Optional[str] = Field(default=None, min_length=1, max_length=MAX_PROCESSOR_TYPE_CHARS)
    split_size: Optional[int] = Field(default=None, ge=1, le=MAX_SPLIT_SIZE)
    split_overlap: Optional[int] = Field(default=None, ge=0, le=MAX_SPLIT_OVERLAP)
    processing_started_at: Optional[datetime] = Field(default=None)
    processing_finished_at: Optional[datetime] = Field(default=None)
    created_by: int = Field(..., gt=0, le=MAX_ID)
    created_at: datetime = Field(...)
    updated_by: Optional[int] = Field(default=None, gt=0, le=MAX_ID)
    updated_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[int] = Field(default=None, gt=0, le=MAX_ID)
    deleted_at: Optional[datetime] = Field(default=None)

    model_config = {
        "from_attributes": True
    }

    @model_validator(mode="after")
    def validate_fields(self) -> "DocumentResponse":
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name must not be blank.")

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
