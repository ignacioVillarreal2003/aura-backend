from pydantic import BaseModel, Field


class PostProcessDocumentJobCommand(BaseModel):
    job_id: str = Field(..., min_length=16, max_length=64)
