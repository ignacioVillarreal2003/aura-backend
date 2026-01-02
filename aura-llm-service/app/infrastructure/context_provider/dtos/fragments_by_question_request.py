from pydantic import BaseModel, Field


class FragmentsByQuestionRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=5000
    )
    fragments_count: int = Field(
        ...,
        ge=1,
        le=100
    )
