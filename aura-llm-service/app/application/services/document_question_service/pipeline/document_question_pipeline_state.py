from dataclasses import dataclass, field
from typing import Optional

from app.domain.dtos.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.message import Message
from app.infrastructure.authentication_provider.dtos.authentication_response import (
    AuthenticationResponse
)


@dataclass
class DocumentQuestionPipelineState:
    authorization: str
    user: AuthenticationResponse
    messages: list[Message] = field(default_factory=list)

    effective_query: Optional[str] = None
    retrieved_fragments: list[str] = field(default_factory=list)

    response: str = ""

    @classmethod
    def from_request(
            cls,
            request: DocumentQuestionRequest,
            authorization: str,
            user: AuthenticationResponse,
    ) -> "DocumentQuestionPipelineState":
        return cls(
            messages=request.messages,
            authorization=authorization,
            user=user,
        )

    @property
    def current_message(self) -> Message:
        return self.messages[-1]

    @property
    def history_messages(self) -> list[Message]:
        return self.messages[:-1]
