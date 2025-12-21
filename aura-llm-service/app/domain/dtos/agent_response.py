from typing import Optional
from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    answer: str = Field(..., description="The agent's response")
    tool_used: Optional[str] = Field(
        default=None,
        description="The name of the tool used, if any"
    )
