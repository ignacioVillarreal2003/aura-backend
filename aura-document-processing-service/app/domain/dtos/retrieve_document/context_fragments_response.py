from typing import List
from pydantic import BaseModel, Field

from app.domain.dtos.retrieve_document.context_fragment_response import ContextFragmentResponse


class ContextFragmentsResponse(BaseModel):
    context_fragments: List[ContextFragmentResponse] = Field(
        default_factory=list
    )
