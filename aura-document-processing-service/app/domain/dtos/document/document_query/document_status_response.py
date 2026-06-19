from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator

from app.domain.field_limits import MAX_ID
from app.domain.types import DocumentId


class DocumentStatusResponse(BaseModel):
    """Lightweight processing-status projection of a document.

    Exposes only the fields a client needs to poll an asynchronous ingestion
    pipeline (chunk -> embed -> enrichment / graph), avoiding the cost of
    transferring the full document on every poll.
    """

    id: DocumentId = Field(..., gt=0, le=MAX_ID)
    status: str = Field(..., min_length=1, max_length=64)
    enrichment_status: str = Field(default="pending", min_length=1, max_length=32)
    graph_status: str = Field(default="pending", min_length=1, max_length=32)
    processing_started_at: Optional[datetime] = Field(default=None)
    processing_finished_at: Optional[datetime] = Field(default=None)

    @model_validator(mode="after")
    def validate_invariants(self) -> "DocumentStatusResponse":
        if self.processing_started_at and self.processing_finished_at:
            if self.processing_finished_at < self.processing_started_at:
                raise ValueError("processing_finished_at cannot be before processing_started_at.")
        return self

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }
