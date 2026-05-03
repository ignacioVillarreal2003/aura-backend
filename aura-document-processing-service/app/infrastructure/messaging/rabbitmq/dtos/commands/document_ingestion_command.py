from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_MIME_TYPE_CHARS, MAX_NAME_CHARS, MAX_STORAGE_URL_CHARS


class DocumentIngestionCommand(BaseModel):
    document_id: int = Field(..., ge=1)
    storage_url: str = Field(..., max_length=MAX_STORAGE_URL_CHARS)
    filename: str = Field(..., max_length=MAX_NAME_CHARS)
    mime_type: str = Field(..., max_length=MAX_MIME_TYPE_CHARS)
    created_by: int = Field(..., ge=1)
    prefer_docling: bool = Field(default=False)
