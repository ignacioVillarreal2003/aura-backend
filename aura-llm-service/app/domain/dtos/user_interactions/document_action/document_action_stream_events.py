from typing import Literal, Union
from pydantic import BaseModel, Field

from app.domain.dtos.user_interactions.document_action.document_action_response import DocumentActionResponse
from app.domain.field_limits import (
    MAX_CODE_CHARS,
    MAX_CONTENT_CHARS,
    MAX_ERROR_MESSAGE_CHARS,
    MAX_MESSAGE_CHARS,
    MAX_STEP_CHARS,
)


class DocumentActionStreamProgress(BaseModel):
    type: Literal["progress"] = "progress"
    step: str = Field(..., min_length=1, max_length=MAX_STEP_CHARS)
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)

    model_config = {"from_attributes": True}


class DocumentActionStreamDelta(BaseModel):
    type: Literal["delta"] = "delta"
    text: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)

    model_config = {"from_attributes": True}


class DocumentActionStreamComplete(BaseModel):
    type: Literal["complete"] = "complete"
    result: DocumentActionResponse = Field(...)

    model_config = {"from_attributes": True}


class DocumentActionStreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str = Field(..., min_length=1, max_length=MAX_ERROR_MESSAGE_CHARS)
    code: str | None = Field(default=None, max_length=MAX_CODE_CHARS)

    model_config = {"from_attributes": True}


DocumentActionStreamEvent = Union[
    DocumentActionStreamProgress,
    DocumentActionStreamDelta,
    DocumentActionStreamComplete,
    DocumentActionStreamError,
]
