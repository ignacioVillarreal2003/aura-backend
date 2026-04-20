from typing import Optional

from pydantic import BaseModel, Field

MAX_MESSAGE_CHARS = 500


class PostProcessDocumentsStartResponse(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)
    total_documents: int = Field(..., ge=0)
    job_id: Optional[str] = Field(default=None, max_length=64)
