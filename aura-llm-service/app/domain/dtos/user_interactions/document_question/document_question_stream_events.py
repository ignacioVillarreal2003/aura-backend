from typing import Literal, Union
from pydantic import BaseModel, Field

from app.domain.dtos.user_interactions.document_question.document_question_response import DocumentQuestionResponse
from app.domain.field_limits import (
    MAX_CODE_CHARS,
    MAX_CONTENT_CHARS,
    MAX_ERROR_MESSAGE_CHARS,
    MAX_MESSAGE_CHARS,
    MAX_QUESTION_CHARS,
    MAX_STEP_CHARS,
)
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


class DocumentQuestionStreamProgress(BaseModel):
    type: Literal["progress"] = "progress"
    step: str = Field(..., min_length=1, max_length=MAX_STEP_CHARS)
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)

    model_config = {"from_attributes": True}


class DocumentQuestionStreamMeta(BaseModel):
    type: Literal["meta"] = "meta"
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_CHARS)
    fragments: list[FragmentResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class DocumentQuestionStreamDelta(BaseModel):
    type: Literal["delta"] = "delta"
    text: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)

    model_config = {"from_attributes": True}


class DocumentQuestionStreamComplete(BaseModel):
    type: Literal["complete"] = "complete"
    result: DocumentQuestionResponse = Field(...)

    model_config = {"from_attributes": True}


class DocumentQuestionStreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str = Field(..., min_length=1, max_length=MAX_ERROR_MESSAGE_CHARS)
    code: str | None = Field(default=None, max_length=MAX_CODE_CHARS)

    model_config = {"from_attributes": True}


DocumentQuestionStreamEvent = Union[
    DocumentQuestionStreamProgress,
    DocumentQuestionStreamMeta,
    DocumentQuestionStreamDelta,
    DocumentQuestionStreamComplete,
    DocumentQuestionStreamError,
]
