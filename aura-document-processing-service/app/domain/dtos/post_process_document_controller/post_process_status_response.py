from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PostProcessDocumentError(BaseModel):
    document_id: int = Field(...)
    error: str = Field(...)


class PostProcessStatusResponse(BaseModel):
    is_running: bool = Field(...)
    total_documents: int = Field(default=0)
    processed_documents: int = Field(default=0)
    failed_documents: int = Field(default=0)
    current_document_id: Optional[int] = Field(default=None)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)
    errors: list[PostProcessDocumentError] = Field(default_factory=list)
