from datetime import datetime
from pydantic import BaseModel, Field

from app.domain.constants.document_mime_type import DocumentMimeType
from app.domain.constants.document_status import DocumentStatus


class CreateDocumentResponse(BaseModel):
    id: int = Field(...)
    name: str = Field(...)
    original_name: str = Field(...)
    mime_type: DocumentMimeType = Field(...)
    status: DocumentStatus = Field(...)
    storage_url: str = Field(...)
    file_size_bytes: int = Field(...)
    is_active: bool = Field(...)
    processing_started_at: datetime = Field(...)
    created_by: int = Field(...)
    created_at: datetime = Field(...)
