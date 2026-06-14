from dataclasses import dataclass, field
from typing import Optional

from app.application.services.user_interactions.document_summary_service.constants.summarization_strategy import SummarizationStrategy
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.document_summary.document_summary_request import DocumentSummaryRequest
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


@dataclass
class DocumentSummaryState:
    document_ids: list[int]
    authenticated_user: AuthenticatedUser

    chat_id: Optional[int] = None
    fragments: list[FragmentResponse] = field(default_factory=list)
    strategy: Optional[SummarizationStrategy] = None
    partial_summaries: list[str] = field(default_factory=list)
    summary: str = ""
    system_prompt: Optional[str] = None
    response_style: Optional[str] = None

    @classmethod
    def from_request(
            cls,
            document_summary_request: DocumentSummaryRequest,
            authenticated_user: AuthenticatedUser,
    ) -> "DocumentSummaryState":
        return cls(
            document_ids=document_summary_request.document_ids,
            authenticated_user=authenticated_user,
            chat_id=document_summary_request.chat_id,
            system_prompt=document_summary_request.system_prompt,
            response_style=document_summary_request.response_style,
        )
