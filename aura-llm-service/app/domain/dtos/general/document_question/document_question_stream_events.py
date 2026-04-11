from typing import Literal, Union

from pydantic import BaseModel, Field

from app.domain.dtos.general.document_question.document_question_response import DocumentQuestionResponse
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


class DocumentQuestionStreamMeta(BaseModel):
    type: Literal["meta"] = "meta"
    question: str = Field(...)
    fragments: list[FragmentResponse] = Field(default_factory=list)


class DocumentQuestionStreamDelta(BaseModel):
    type: Literal["delta"] = "delta"
    text: str = Field(...)


class DocumentQuestionStreamComplete(BaseModel):
    type: Literal["complete"] = "complete"
    result: DocumentQuestionResponse = Field(...)


class DocumentQuestionStreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str = Field(...)
    code: str | None = Field(default=None)


DocumentQuestionStreamEvent = Union[
    DocumentQuestionStreamMeta,
    DocumentQuestionStreamDelta,
    DocumentQuestionStreamComplete,
    DocumentQuestionStreamError,
]
