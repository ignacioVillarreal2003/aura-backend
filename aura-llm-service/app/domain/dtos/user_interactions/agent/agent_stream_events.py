from typing import Literal, Union
from pydantic import BaseModel, Field

from app.domain.dtos.user_interactions.agent.agent_response import AgentResponse
from app.domain.field_limits import MAX_CONTENT_CHARS


class AgentStreamProgress(BaseModel):
    type: Literal["progress"] = "progress"
    step: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)

    model_config = {"from_attributes": True}


class AgentStreamComplete(BaseModel):
    type: Literal["complete"] = "complete"
    result: AgentResponse = Field(...)

    model_config = {"from_attributes": True}


class AgentStreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)
    code: str | None = Field(default=None)

    model_config = {"from_attributes": True}


AgentStreamEvent = Union[AgentStreamProgress, AgentStreamComplete, AgentStreamError]
