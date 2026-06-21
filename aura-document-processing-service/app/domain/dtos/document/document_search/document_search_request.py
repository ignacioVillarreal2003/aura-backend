from pydantic import BaseModel, Field, field_validator

from app.domain.constants.document.document_search_mode import DocumentSearchMode
from app.domain.field_limits import (
    DEFAULT_DOCUMENT_SEARCH_PAGE_SIZE,
    MAX_DOCUMENT_SEARCH_PAGE,
    MAX_DOCUMENT_SEARCH_PAGE_SIZE,
    MAX_DOCUMENT_SEARCH_QUERY_CHARS,
)


class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_DOCUMENT_SEARCH_QUERY_CHARS)
    mode: DocumentSearchMode = Field(default=DocumentSearchMode.vector)
    page: int = Field(default=1, ge=1, le=MAX_DOCUMENT_SEARCH_PAGE)
    page_size: int = Field(
        default=DEFAULT_DOCUMENT_SEARCH_PAGE_SIZE,
        ge=1,
        le=MAX_DOCUMENT_SEARCH_PAGE_SIZE,
    )

    @field_validator("query")
    @classmethod
    def clean_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be blank.")
        return v

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    model_config = {"frozen": True}
