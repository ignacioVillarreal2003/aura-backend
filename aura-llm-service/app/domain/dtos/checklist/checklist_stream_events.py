from typing import Literal, Union

from pydantic import BaseModel, Field

from app.domain.dtos.checklist.checklist_response import ChecklistGenerateResponse


class ChecklistStreamProgress(BaseModel):
    type: Literal["progress"] = "progress"
    step: str = Field(...)
    message: str = Field(...)

    model_config = {"from_attributes": True}


class ChecklistStreamComplete(BaseModel):
    type: Literal["complete"] = "complete"
    result: ChecklistGenerateResponse = Field(...)

    model_config = {"from_attributes": True}


class ChecklistStreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str = Field(...)
    code: str | None = Field(default=None)

    model_config = {"from_attributes": True}


ChecklistStreamEvent = Union[ChecklistStreamProgress, ChecklistStreamComplete, ChecklistStreamError]
