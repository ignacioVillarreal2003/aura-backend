from pydantic import BaseModel, Field


class PostProcessFragmentStartResponse(BaseModel):
    message: str = Field(...)
    total_fragments: int = Field(...)
