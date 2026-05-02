from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.domain.dtos.graph.graph_field_limits import (
    MAX_KG_ERROR_MESSAGE_CHARS,
    MAX_KNOWLEDGE_GRAPH_ERRORS,
)
from app.domain.field_limits import MAX_ID


class GraphExtractionError(BaseModel):
    fragment_id: int = Field(..., ge=1, le=MAX_ID)
    error: str = Field(..., min_length=1, max_length=MAX_KG_ERROR_MESSAGE_CHARS)


class GraphExtractionProgressResponse(BaseModel):
    job_id: Optional[str] = Field(default=None, min_length=16, max_length=64)
    document_id: Optional[int] = Field(default=None, ge=1, le=MAX_ID)
    is_running: bool = Field(...)
    total_fragments: int = Field(..., ge=0)
    processed_fragments: int = Field(..., ge=0)
    failed_fragments: int = Field(..., ge=0)
    extracted_entities: int = Field(..., ge=0)
    extracted_relations: int = Field(..., ge=0)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)
    errors: list[GraphExtractionError] = Field(
        default_factory=list, max_length=MAX_KNOWLEDGE_GRAPH_ERRORS
    )
