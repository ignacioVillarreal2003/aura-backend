from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_LLM_CONTEXTUAL_PREFIX_CHARS


class ContextualizeFragmentResponse(BaseModel):
    context: str = Field(..., min_length=1, max_length=MAX_LLM_CONTEXTUAL_PREFIX_CHARS)
