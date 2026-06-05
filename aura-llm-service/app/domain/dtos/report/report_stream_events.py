from typing import Literal, Union

from pydantic import BaseModel, Field

from app.domain.dtos.report.report_response import ReportGenerateResponse


class ReportStreamProgress(BaseModel):
    type: Literal["progress"] = "progress"
    step: str = Field(...)
    message: str = Field(...)

    model_config = {"from_attributes": True}


class ReportStreamComplete(BaseModel):
    type: Literal["complete"] = "complete"
    result: ReportGenerateResponse = Field(...)

    model_config = {"from_attributes": True}


class ReportStreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str = Field(...)
    code: str | None = Field(default=None)

    model_config = {"from_attributes": True}


ReportStreamEvent = Union[ReportStreamProgress, ReportStreamComplete, ReportStreamError]
