from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.domain.constants.document.bulk_operation import BulkOperation
from app.domain.field_limits import (
    MAX_ID,
    MAX_JOB_ID_CHARS,
    MAX_POST_PROCESS_DOCUMENT_IDS,
    MAX_POST_PROCESS_ERROR_MESSAGE_CHARS,
    MAX_POST_PROCESS_SNAPSHOT_ERRORS,
)


class BulkJobError(BaseModel):
    document_id: Optional[int] = Field(default=None, ge=1, le=MAX_ID)
    error: str = Field(..., min_length=1, max_length=MAX_POST_PROCESS_ERROR_MESSAGE_CHARS)


class BulkStartResponse(BaseModel):
    job_id: str = Field(..., min_length=1, max_length=MAX_JOB_ID_CHARS)
    operation: BulkOperation = Field(...)
    total: int = Field(..., ge=0, le=MAX_POST_PROCESS_DOCUMENT_IDS)
    queued: bool = Field(default=True)


class BulkJobStatusResponse(BaseModel):
    job_id: Optional[str] = Field(default=None, max_length=MAX_JOB_ID_CHARS)
    operation: BulkOperation = Field(...)
    is_running: bool = Field(...)
    stop_requested: bool = Field(default=False)
    total: int = Field(..., ge=0)
    processed: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)
    errors: list[BulkJobError] = Field(
        default_factory=list, max_length=MAX_POST_PROCESS_SNAPSHOT_ERRORS
    )
