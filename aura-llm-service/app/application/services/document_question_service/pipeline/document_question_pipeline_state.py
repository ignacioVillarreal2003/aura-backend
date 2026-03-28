from dataclasses import dataclass, field
from typing import Optional

from app.domain.dtos.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.message import Message
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.document_context_provider.dtos.context_fragments_response import ContextFragmentResponse


@dataclass
class DocumentQuestionPipelineState:
    authenticated_user: AuthenticationResponse
    messages: list[Message] = field(default_factory=list)

    retrieval_query: Optional[str] = None
    retrieved_fragments: list[ContextFragmentResponse] = field(default_factory=list)
    rerank_fragments: list[ContextFragmentResponse] = field(default_factory=list)
    answer: str = ""

    @classmethod
    def from_request(
            cls,
            request: DocumentQuestionRequest,
            authenticated_user: AuthenticationResponse,
    ) -> "DocumentQuestionPipelineState":
        return cls(
            messages=request.messages,
            authenticated_user=authenticated_user,
        )

    @property
    def current_message(self) -> Message:
        return self.messages[-1]

    @property
    def history_messages(self) -> list[Message]:
        return self.messages[:-1]
