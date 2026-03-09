from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.domain.constants.document_mime_type import DocumentMimeType
from app.domain.constants.document_status import DocumentStatus
from app.domain.constants.document_type import DocumentType


class PostProcessDocumentResponse(BaseModel):
    id: int
    chat_id: Optional[int] = None,
    name: str
    description: Optional[str] = None
    mime_type: DocumentMimeType
    status: DocumentStatus
    storage_url: str
    file_size_bytes: int
    type: Optional[DocumentType] = None
    category: Optional[str] = None
    text_cleaner_type: Optional[str] = None
    text_splitter_type: Optional[str] = None
    embedder_type: Optional[str] = None
    split_size: Optional[int] = None
    split_overlap: Optional[int] = None
    processing_started_at: Optional[datetime] = None
    processing_finished_at: Optional[datetime] = None
    created_by: int
    created_at: datetime
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None
    deleted_by: Optional[int] = None
    deleted_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }
