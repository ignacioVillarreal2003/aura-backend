from pydantic import BaseModel, Field

from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_MESSAGES_IN_REQUEST
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


class AgentResponse(BaseModel):
    messages: list[Message] = Field(..., min_length=1, max_length=MAX_MESSAGES_IN_REQUEST)
    fragments: list[FragmentResponse] = Field(default_factory=list)

    model_config = {
        "from_attributes": True
    }
