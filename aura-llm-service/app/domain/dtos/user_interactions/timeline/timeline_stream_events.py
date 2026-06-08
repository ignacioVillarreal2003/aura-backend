from typing import Literal, Union
from pydantic import BaseModel, Field

from app.domain.dtos.user_interactions.timeline.timeline_response import TimelineGenerateResponse
from app.domain.field_limits import MAX_CODE_CHARS, MAX_ERROR_MESSAGE_CHARS, MAX_MESSAGE_CHARS, MAX_STEP_CHARS


class TimelineStreamProgress(BaseModel):
    type: Literal["progress"] = "progress"
    step: str = Field(..., min_length=1, max_length=MAX_STEP_CHARS)
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)

    model_config = {"from_attributes": True}


class TimelineStreamComplete(BaseModel):
    type: Literal["complete"] = "complete"
    result: TimelineGenerateResponse = Field(...)

    model_config = {"from_attributes": True}


class TimelineStreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str = Field(..., min_length=1, max_length=MAX_ERROR_MESSAGE_CHARS)
    code: str | None = Field(default=None, max_length=MAX_CODE_CHARS)

    model_config = {"from_attributes": True}


TimelineStreamEvent = Union[TimelineStreamProgress, TimelineStreamComplete, TimelineStreamError]
