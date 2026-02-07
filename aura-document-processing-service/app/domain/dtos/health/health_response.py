from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(...)
    app: str = Field(...)
    version: str = Field(...)
