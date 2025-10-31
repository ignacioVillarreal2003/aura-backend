from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Fragment(BaseModel):
    id: Optional[int] = Field(None)
    source_document_id: int = Field(...)
    vector: Optional[list[float]] = Field(None)
    content: str = Field(...)
    fragment_index: int = Field(...)
    embedding_model: Optional[str] = Field(None, max_length=255)
    chunk_size: int = Field(...)

    created_by: int = Field(...)
    created_date: datetime = Field(default_factory=datetime.now)
    updated_by: Optional[int] = Field(None)
    updated_date: Optional[datetime] = Field(None)
    deleted_by: Optional[int] = Field(None)
    deleted_date: Optional[datetime] = Field(None)
