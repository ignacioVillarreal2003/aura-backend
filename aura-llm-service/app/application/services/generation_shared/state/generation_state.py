from dataclasses import dataclass, field
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.infrastructure.http.document_context_provider.dtos.fragment_list_response import (
    FragmentSectionGroup,
)
from app.domain.dtos.message import Message


@dataclass
class GenerationState:
    authenticated_user: AuthenticatedUser
    messages: list[Message]
    chat_id: int
    retrieve_context: bool = False
    process_documents: bool = False
    document_ids: list[int] = field(default_factory=list)

    attached_fragments: list[FragmentResponse] = field(default_factory=list)

    base_question: Optional[str] = None
    keyword_question: Optional[str] = None

    fragments: list[FragmentResponse] = field(default_factory=list)

    section_groups: Optional[list[FragmentSectionGroup]] = None
    section_summary: Optional[str] = None

    reduced_context: Optional[str] = None
    history_summary: Optional[str] = None

    reformulation_degraded: bool = False
    retrieval_degraded: bool = False
    reduction_degraded: bool = False
    attached_degraded: bool = False

    @classmethod
    def create(
            cls,
            messages: list[Message],
            chat_id: int,
            authenticated_user: AuthenticatedUser,
            document_ids: Optional[list[int]] = None,
            retrieve_context: bool = False,
            process_documents: bool = False,
    ) -> "GenerationState":
        return cls(
            authenticated_user=authenticated_user,
            messages=list(messages),
            chat_id=chat_id,
            retrieve_context=retrieve_context,
            process_documents=process_documents,
            document_ids=list(document_ids or []),
        )

    @property
    def current_message(self) -> Message:
        return self.messages[-1]

    @property
    def history_messages(self) -> list[Message]:
        return self.messages[:-1]

    @property
    def rag_only_fragments(self) -> list[FragmentResponse]:
        attached_ids = {f.id for f in self.attached_fragments}
        return [f for f in self.fragments if f.id not in attached_ids]

    @property
    def all_fragments(self) -> list[FragmentResponse]:
        return [*self.attached_fragments, *self.rag_only_fragments]
