from pydantic import BaseModel, Field
from typing import List, Optional


class SummaryRequest(BaseModel):
    document_id: int = Field(...)
    chunks: List[str] = Field(...)
    target_length: int = 800
