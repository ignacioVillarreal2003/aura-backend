from typing import Literal, Union

from pydantic import BaseModel, Field

from app.domain.dtos.quiz.quiz_response import QuizGenerateResponse


class QuizStreamProgress(BaseModel):
    type: Literal["progress"] = "progress"
    step: str = Field(...)
    message: str = Field(...)

    model_config = {"from_attributes": True}


class QuizStreamComplete(BaseModel):
    type: Literal["complete"] = "complete"
    result: QuizGenerateResponse = Field(...)

    model_config = {"from_attributes": True}


class QuizStreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str = Field(...)
    code: str | None = Field(default=None)

    model_config = {"from_attributes": True}


QuizStreamEvent = Union[QuizStreamProgress, QuizStreamComplete, QuizStreamError]
