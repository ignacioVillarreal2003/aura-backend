from dataclasses import dataclass, field
from typing import Optional

from app.application.services.document_action_service.constants.processing_strategy import ProcessingStrategy
from app.domain.constants.document_action_type import DocumentActionType
from app.domain.dtos.document_action.document_action_request import DocumentActionRequest
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.document_context_provider.dtos.context_fragments_response import ContextFragmentResponse


@dataclass
class DocumentActionPipelineState:
    document_ids: list[int]
    instruction: str
    action: Optional[DocumentActionType]
    authenticated_user: AuthenticationResponse

    fragments_by_document: dict[int, list[ContextFragmentResponse]] = field(default_factory=dict)
    all_fragments: list[ContextFragmentResponse] = field(default_factory=list)
    strategy: Optional[ProcessingStrategy] = None
    partial_results: list[str] = field(default_factory=list)
    result: str = ""

    @classmethod
    def from_request(
            cls,
            request: DocumentActionRequest,
            authenticated_user: AuthenticationResponse,
    ) -> "DocumentActionPipelineState":
        return cls(
            document_ids=request.document_ids,
            instruction=request.instruction,
            action=request.action,
            authenticated_user=authenticated_user,
        )
