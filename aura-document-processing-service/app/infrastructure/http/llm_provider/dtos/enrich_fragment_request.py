from pydantic import BaseModel, Field


class EnrichFragmentRequest(BaseModel):
    content: str = Field(...)
