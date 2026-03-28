from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PostProcessFragmentError(BaseModel):
    fragment_id: int = Field(...)
    error: str = Field(...)


class PostProcessFragmentStatusResponse(BaseModel):
    is_running: bool = Field(...)
    total_fragments: int = Field(default=0)
    processed_fragments: int = Field(default=0)
    failed_fragments: int = Field(default=0)
    current_fragment_id: Optional[int] = Field(default=None)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)
    errors: list[PostProcessFragmentError] = Field(default_factory=list)
