from typing import Optional
from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_FRAGMENT_CONTENT_CHARS, MAX_ID
from app.domain.types import DocumentId


class DocumentSimilarityHit(BaseModel):
    document_id: DocumentId = Field(..., gt=0, le=MAX_ID)
    score: float = Field(..., ge=0.0)
    matched_fragments: int = Field(..., ge=1)
    best_fragment_content: Optional[str] = Field(default=None, max_length=MAX_FRAGMENT_CONTENT_CHARS)

    model_config = {"frozen": True}
