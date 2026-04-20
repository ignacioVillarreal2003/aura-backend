from datetime import datetime
from pydantic import BaseModel, Field, model_validator

from app.domain.constants.document.document_mime_type import DocumentMimeType
from app.domain.constants.document.document_status import DocumentStatus

MAX_ID = 2_147_483_647
MAX_NAME_CHARS = 255
MAX_STORAGE_URL_CHARS = 1_024
MIN_FILE_SIZE_BYTES = 1


class CreateDocumentResponse(BaseModel):
    id: int = Field(..., gt=0, le=MAX_ID)
    name: str = Field(..., min_length=1, max_length=MAX_NAME_CHARS)
    mime_type: DocumentMimeType = Field(...)
    status: DocumentStatus = Field(...)
    storage_url: str = Field(..., min_length=1, max_length=MAX_STORAGE_URL_CHARS)
    file_size_bytes: int = Field(..., ge=MIN_FILE_SIZE_BYTES)
    processing_started_at: datetime = Field(...)
    created_by: int = Field(..., gt=0, le=MAX_ID)
    created_at: datetime = Field(...)

    model_config = {
        "from_attributes": True
    }

    @model_validator(mode="after")
    def validate_fields(self) -> "CreateDocumentResponse":
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name must not be blank.")
        if self.processing_started_at > self.created_at:
            raise ValueError("processing_started_at cannot be after created_at.")
        return self
