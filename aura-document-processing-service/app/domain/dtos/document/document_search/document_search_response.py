from typing import Optional
from pydantic import BaseModel, Field

from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.field_limits import (
    MAX_DOCUMENT_SEARCH_RESULTS,
    MAX_DOCUMENT_SEARCH_SNIPPET_CHARS,
)


class DocumentSearchResultResponse(BaseModel):
    document: DocumentResponse
    similarity: float = Field(..., ge=0.0, le=1.0)
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
        max_length=MAX_DOCUMENT_SEARCH_RESULTS,
    )

    model_config = {
        "from_attributes": True,
        "frozen": True,
    }
