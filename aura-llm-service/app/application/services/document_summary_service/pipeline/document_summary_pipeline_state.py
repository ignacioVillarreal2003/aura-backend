from dataclasses import dataclass, field
from typing import Optional

from app.application.services.document_summary_service.constants.summarization_strategy import SummarizationStrategy
from app.domain.dtos.document_summary.document_summary_request import DocumentSummaryRequest
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.document_context_provider.dtos.context_fragments_response import ContextFragmentResponse


@dataclass
class DocumentSummaryPipelineState:
    document_id: int
    authenticated_user: AuthenticationResponse

    fragments: list[ContextFragmentResponse] = field(default_factory=list)
    strategy: Optional[SummarizationStrategy] = None
    partial_summaries: list[str] = field(default_factory=list)
    summary: str = ""

    @classmethod
    def from_request(
            cls,
            request: DocumentSummaryRequest,
            authenticated_user: AuthenticationResponse,
    ) -> "DocumentSummaryPipelineState":
        return cls(
            document_id=request.document_id,
            authenticated_user=authenticated_user,
        )
