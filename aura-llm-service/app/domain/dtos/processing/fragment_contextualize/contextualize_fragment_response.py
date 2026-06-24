from pydantic import BaseModel, Field, field_validator

from app.domain.field_limits import MAX_CONTEXTUAL_PREFIX_CHARS
from app.domain.validation import stripped_non_blank


class ContextualizeFragmentResponse(BaseModel):
    context: str = Field(..., min_length=1, max_length=MAX_CONTEXTUAL_PREFIX_CHARS)

    @field_validator("context")
    @classmethod
    def _strip_context(cls, value: str) -> str:
        return stripped_non_blank(value, "Context must not be blank.")

    model_config = {"from_attributes": True}
