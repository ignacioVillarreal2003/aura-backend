from dataclasses import dataclass, field
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.message import Message
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


@dataclass
class DocumentQuestionState:
    authenticated_user: AuthenticatedUser
    messages: list[Message] = field(default_factory=list)

    chat_id: Optional[int] = None
    document_ids: list[int] = field(default_factory=list)

    system_prompt: Optional[str] = None
    response_style: Optional[str] = None

    base_question: Optional[str] = None
    keyword_question: Optional[str] = None

    attached_fragments: list[FragmentResponse] = field(default_factory=list)
    fragments: list[FragmentResponse] = field(default_factory=list)
    reduced_attached_context: Optional[str] = None

    answer: str = ""

    @classmethod
    def from_request(
            cls,
            document_question_request: DocumentQuestionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> "DocumentQuestionState":
        return cls(
            messages=document_question_request.messages,
            authenticated_user=authenticated_user,
            chat_id=document_question_request.chat_id,
            document_ids=list(document_question_request.document_ids),
            system_prompt=document_question_request.system_prompt,
            response_style=document_question_request.response_style,
        )

    @property
    def current_message(self) -> Message:
        return self.messages[-1]

    @property
    def history_messages(self) -> list[Message]:
        return self.messages[:-1]

    @property
    def all_fragments(self) -> list[FragmentResponse]:
        attached_ids = {f.id for f in self.attached_fragments}
        rag_only = [f for f in self.fragments if f.id not in attached_ids]
        return [*self.attached_fragments, *rag_only]
