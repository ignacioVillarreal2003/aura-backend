from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.domain.dtos.document.post_process_document.post_process_document_error import PostProcessDocumentError
from app.domain.field_limits import MAX_ID, MAX_JOB_ID_CHARS, MAX_POST_PROCESS_SNAPSHOT_ERRORS
from app.domain.types import DocumentId


class PostProcessDocumentsStatusResponse(BaseModel):
    job_id: Optional[str] = Field(default=None, max_length=MAX_JOB_ID_CHARS)
    is_running: bool = Field(...)
    total_documents: int = Field(default=0, ge=0)
    processed_documents: int = Field(default=0, ge=0)
    failed_documents: int = Field(default=0, ge=0)
    current_document_id: Optional[DocumentId] = Field(default=None, gt=0, le=MAX_ID)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)
    errors: list[PostProcessDocumentError] = Field(
        default_factory=list, max_length=MAX_POST_PROCESS_SNAPSHOT_ERRORS
    )

    @model_validator(mode="after")
    def validate_status_snapshot(self) -> "PostProcessDocumentsStatusResponse":
        if self.processed_documents + self.failed_documents > self.total_documents:
            raise ValueError("processed_documents + failed_documents cannot exceed total_documents.")
        if self.started_at and self.finished_at and self.finished_at < self.started_at:
            raise ValueError("finished_at cannot be before started_at.")
        if self.is_running and self.finished_at is not None:
            raise ValueError("finished_at must be absent while the process is still running.")
        if not self.is_running and self.current_document_id is not None:
            raise ValueError("current_document_id must be absent when the process is not running.")
        return self

    model_config = {
        "frozen": True,
    }
