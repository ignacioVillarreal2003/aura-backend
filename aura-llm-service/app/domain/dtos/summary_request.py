from pydantic import BaseModel, Field
from typing import List


class SummaryRequest(BaseModel):
    fragments: List[str] = Field(...)