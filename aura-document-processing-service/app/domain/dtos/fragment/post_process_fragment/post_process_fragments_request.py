from pydantic import BaseModel, Field


class PostProcessFragmentsRequest(BaseModel):
    document_ids: list[int] = Field(..., min_length=1)
