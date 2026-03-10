from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    answer: str = Field(
        ...
    )
