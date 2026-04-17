from dataclasses import dataclass, field
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.general.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.message import Message
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


@dataclass
class DocumentQuestionPipelineState:
    authenticated_user: AuthenticatedUser
    messages: list[Message] = field(default_factory=list)

    question_with_history: Optional[str] = None
    retrieval_keywords: Optional[str] = None

    retrieved_fragments: list[FragmentResponse] = field(default_factory=list)

    answer: str = ""

    @classmethod
    def from_request(
        cls,
        request: DocumentQuestionRequest,
        authenticated_user: AuthenticatedUser
    ) -> "DocumentQuestionPipelineState":
        return cls(
            messages=request.messages,
            authenticated_user=authenticated_user,
        )

    @property
    def current_message(
            self
    ) -> Message:
        return self.messages[-1]

    @property
    def history_messages(
            self
    ) -> list[Message]:
        return self.messages[:-1]

    @property
    def effective_question(
            self
    ) -> str:
        return self.question_with_history or self.current_message.content