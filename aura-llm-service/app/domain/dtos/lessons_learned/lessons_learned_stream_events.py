from typing import Literal, Union

from pydantic import BaseModel, Field

from app.domain.dtos.lessons_learned.lessons_learned_response import LessonsLearnedGenerateResponse


class LessonsLearnedStreamProgress(BaseModel):
    type: Literal["progress"] = "progress"
    step: str = Field(...)
    message: str = Field(...)

    model_config = {"from_attributes": True}


class LessonsLearnedStreamComplete(BaseModel):
    type: Literal["complete"] = "complete"
    result: LessonsLearnedGenerateResponse = Field(...)

    model_config = {"from_attributes": True}


class LessonsLearnedStreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str = Field(...)
    code: str | None = Field(default=None)

    model_config = {"from_attributes": True}


LessonsLearnedStreamEvent = Union[
    LessonsLearnedStreamProgress,
    LessonsLearnedStreamComplete,
    LessonsLearnedStreamError,
]
