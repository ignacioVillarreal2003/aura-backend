from typing import Literal, Union

from pydantic import BaseModel, Field

from app.domain.dtos.document_summary.document_summary_response import DocumentSummaryResponse
from app.domain.field_limits import MAX_CONTENT_CHARS


class DocumentSummaryStreamProgress(BaseModel):
    type: Literal["progress"] = "progress"
    step: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)

    model_config = {"from_attributes": True}


class DocumentSummaryStreamDelta(BaseModel):
    type: Literal["delta"] = "delta"
    text: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)

    model_config = {"from_attributes": True}


class DocumentSummaryStreamComplete(BaseModel):
    type: Literal["complete"] = "complete"
    result: DocumentSummaryResponse = Field(...)

    model_config = {"from_attributes": True}


class DocumentSummaryStreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)
    code: str | None = Field(default=None)

    model_config = {"from_attributes": True}


DocumentSummaryStreamEvent = Union[
    DocumentSummaryStreamProgress,
    DocumentSummaryStreamDelta,
    DocumentSummaryStreamComplete,
    DocumentSummaryStreamError,
]
