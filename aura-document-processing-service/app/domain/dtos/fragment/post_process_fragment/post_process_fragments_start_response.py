from pydantic import BaseModel, Field


class PostProcessFragmentsStartResponse(BaseModel):
    message: str = Field(...)
    total_fragments: int = Field(...)
