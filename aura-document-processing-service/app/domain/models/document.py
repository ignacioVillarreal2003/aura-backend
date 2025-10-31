from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.domain.constants.document_status import DocumentStatus
from app.domain.constants.document_type import DocumentType
from app.domain.constants.embedding_status import EmbeddingStatus


class Document(BaseModel):
    id: Optional[int] = Field(None)
    title: str = Field(..., max_length=255)
    type: DocumentType = Field(...)
    status: DocumentStatus = Field(DocumentStatus.pending)
    path: Optional[str] = Field(None, max_length=255)

    size: Optional[int] = Field(None)

    created_by: int = Field(...)
    created_date: datetime = Field(default_factory=datetime.now)
    updated_by: Optional[int] = Field(None)
    updated_date: Optional[datetime] = Field(None)
    deleted_by: Optional[int] = Field(None)
    deleted_date: Optional[datetime] = Field(None)

    embedding_status: EmbeddingStatus = Field(EmbeddingStatus.pending)
    vector_count: Optional[int] = Field(None)
    hash: Optional[str] = Field(None)