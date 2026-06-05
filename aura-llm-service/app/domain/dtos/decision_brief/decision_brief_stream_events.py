from typing import Literal, Union

from pydantic import BaseModel, Field

from app.domain.dtos.decision_brief.decision_brief_response import DecisionBriefGenerateResponse


class DecisionBriefStreamProgress(BaseModel):
    type: Literal["progress"] = "progress"
    step: str = Field(...)
    message: str = Field(...)

    model_config = {"from_attributes": True}


class DecisionBriefStreamComplete(BaseModel):
    type: Literal["complete"] = "complete"
    result: DecisionBriefGenerateResponse = Field(...)

    model_config = {"from_attributes": True}


class DecisionBriefStreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str = Field(...)
    code: str | None = Field(default=None)

    model_config = {"from_attributes": True}


DecisionBriefStreamEvent = Union[
    DecisionBriefStreamProgress,
    DecisionBriefStreamComplete,
    DecisionBriefStreamError,
]
