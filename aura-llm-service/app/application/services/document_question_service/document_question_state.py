from dataclasses import dataclass, field
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.message import Message
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


@dataclass
class DocumentQuestionState:
    authenticated_user: AuthenticatedUser
    messages: list[Message] = field(default_factory=list)

    base_question: Optional[str] = None
    keyword_question: Optional[str] = None

    fragments: list[FragmentResponse] = field(default_factory=list)

    answer: str = ""

    @classmethod
    def from_request(
            cls,
            document_question_request: DocumentQuestionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentQuestionState:
        return cls(
            messages=document_question_request.messages,
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
