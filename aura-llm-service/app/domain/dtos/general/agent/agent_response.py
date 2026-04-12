from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    message: str = Field(...)

    model_config = {
        "from_attributes": True
    }
