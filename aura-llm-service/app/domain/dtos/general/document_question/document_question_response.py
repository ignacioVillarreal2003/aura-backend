from dataclasses import field
from pydantic import BaseModel, Field

from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


class DocumentQuestionResponse(BaseModel):
    question: str = Field(...)
    answer: str = Field(...)
    fragments: list[FragmentResponse] = field(default_factory=list)

    model_config = {
        "from_attributes": True
    }
