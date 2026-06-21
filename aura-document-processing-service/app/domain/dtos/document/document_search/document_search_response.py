from typing import Optional
from pydantic import BaseModel, Field

from app.domain.constants.document.document_search_mode import DocumentSearchMode
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.field_limits import (
    MAX_DOCUMENT_SEARCH_PAGE_SIZE,
    MAX_DOCUMENT_SEARCH_SNIPPET_CHARS,
)


class DocumentSearchResultResponse(BaseModel):
    document: DocumentResponse
    similarity: float = Field(..., ge=0.0, le=1.0)
    score: float = Field(...)
    matched_fragments: int = Field(..., ge=1)
    best_fragment_snippet: Optional[str] = Field(
        default=None,
        max_length=MAX_DOCUMENT_SEARCH_SNIPPET_CHARS,
    )

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }


class DocumentSearchListResponse(BaseModel):
    results: list[DocumentSearchResultResponse] = Field(
        default_factory=list,
        max_length=MAX_DOCUMENT_SEARCH_PAGE_SIZE,
    )
    mode: DocumentSearchMode = Field(default=DocumentSearchMode.vector)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=MAX_DOCUMENT_SEARCH_PAGE_SIZE, ge=1)
    has_more: bool = Field(default=False)

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }
