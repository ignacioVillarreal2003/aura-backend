from typing import List
from pydantic import BaseModel, Field


class ContextFragmentsResponse(BaseModel):
    context_fragments: List[str] = Field(...)
