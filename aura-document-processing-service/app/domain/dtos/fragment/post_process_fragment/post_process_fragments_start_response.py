from typing import Optional
from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_MESSAGE_CHARS


class PostProcessFragmentsStartResponse(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)
    total_fragments: int = Field(..., ge=0)
    job_id: Optional[str] = Field(default=None, max_length=64)

    model_config = {"frozen": True}
