from pydantic import BaseModel, Field, field_validator

from app.domain.field_limits import (
    DEFAULT_DOCUMENT_SEARCH_RESULTS,
    MAX_DOCUMENT_SEARCH_QUERY_CHARS,
    MAX_DOCUMENT_SEARCH_RESULTS,
)


class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_DOCUMENT_SEARCH_QUERY_CHARS)
    max_documents: int = Field(
        default=DEFAULT_DOCUMENT_SEARCH_RESULTS,
        ge=1,
        le=MAX_DOCUMENT_SEARCH_RESULTS,
    )

    @field_validator("query")
    @classmethod
    def clean_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be blank.")
        return v

    model_config = {"frozen": True}
