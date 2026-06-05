from typing import Literal, Union

from pydantic import BaseModel, Field

from app.domain.dtos.timeline.timeline_response import TimelineGenerateResponse


class TimelineStreamProgress(BaseModel):
    type: Literal["progress"] = "progress"
    step: str = Field(...)
    message: str = Field(...)

    model_config = {"from_attributes": True}


class TimelineStreamComplete(BaseModel):
    type: Literal["complete"] = "complete"
    result: TimelineGenerateResponse = Field(...)

    model_config = {"from_attributes": True}


class TimelineStreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str = Field(...)
    code: str | None = Field(default=None)

    model_config = {"from_attributes": True}


TimelineStreamEvent = Union[TimelineStreamProgress, TimelineStreamComplete, TimelineStreamError]
