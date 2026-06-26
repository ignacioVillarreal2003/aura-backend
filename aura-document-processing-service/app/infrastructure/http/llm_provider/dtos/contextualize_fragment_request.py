from pydantic import BaseModel, Field

from app.domain.field_limits import (
    MAX_LLM_CONTEXTUALIZE_CONTENT_CHARS,
    MAX_LLM_CONTEXTUALIZE_SUMMARY_CHARS,
)


class ContextualizeFragmentRequest(BaseModel):
    document_summary: str = Field(..., min_length=1, max_length=MAX_LLM_CONTEXTUALIZE_SUMMARY_CHARS)
    content: str = Field(..., min_length=1, max_length=MAX_LLM_CONTEXTUALIZE_CONTENT_CHARS)
