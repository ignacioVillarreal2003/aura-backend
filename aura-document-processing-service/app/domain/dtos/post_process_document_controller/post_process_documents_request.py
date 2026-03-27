from pydantic import BaseModel, Field


class PostProcessDocumentsRequest(BaseModel):
    document_ids: list[int] = Field(..., min_length=1)
