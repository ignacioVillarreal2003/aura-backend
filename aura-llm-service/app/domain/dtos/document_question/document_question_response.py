from dataclasses import field
from pydantic import BaseModel, Field

from app.infrastructure.document_context_provider.dtos.context_fragments_response import ContextFragmentResponse


class DocumentQuestionResponse(BaseModel):
    question: str = Field(...)
    answer: str = Field(...)
    fragments: list[ContextFragmentResponse] = field(default_factory=list)

    model_config = {
        "from_attributes": True
    }
