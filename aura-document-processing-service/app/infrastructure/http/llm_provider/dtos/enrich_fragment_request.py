from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_LLM_ENRICH_CONTENT_CHARS


class EnrichFragmentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=MAX_LLM_ENRICH_CONTENT_CHARS)
