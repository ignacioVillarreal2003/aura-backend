from typing import Literal, Union
from pydantic import BaseModel, Field

from app.domain.dtos.user_interactions.general_chat.general_chat_response import GeneralChatResponse
from app.domain.field_limits import (
    MAX_CODE_CHARS,
    MAX_CONTENT_CHARS,
    MAX_ERROR_MESSAGE_CHARS,
    MAX_MESSAGE_CHARS,
    MAX_STEP_CHARS,
)


class GeneralChatStreamProgress(BaseModel):
    type: Literal["progress"] = "progress"
    step: str = Field(..., min_length=1, max_length=MAX_STEP_CHARS)
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)

    model_config = {"from_attributes": True}


class GeneralChatStreamDelta(BaseModel):
    type: Literal["delta"] = "delta"
    text: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)

    model_config = {"from_attributes": True}


class GeneralChatStreamComplete(BaseModel):
    type: Literal["complete"] = "complete"
    result: GeneralChatResponse = Field(...)

    model_config = {"from_attributes": True}


class GeneralChatStreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str = Field(..., min_length=1, max_length=MAX_ERROR_MESSAGE_CHARS)
    code: str | None = Field(default=None, max_length=MAX_CODE_CHARS)

    model_config = {"from_attributes": True}


GeneralChatStreamEvent = Union[
    GeneralChatStreamProgress,
    GeneralChatStreamDelta,
    GeneralChatStreamComplete,
    GeneralChatStreamError,
]
