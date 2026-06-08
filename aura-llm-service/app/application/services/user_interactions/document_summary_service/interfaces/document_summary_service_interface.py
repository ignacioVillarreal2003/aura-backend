from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.user_interactions.document_summary.document_summary_response import DocumentSummaryResponse
from app.domain.dtos.user_interactions.document_summary.document_summary_stream_events import DocumentSummaryStreamEvent


class DocumentSummaryServiceInterface(ABC):
    @abstractmethod
    async def execute_document_summary(
            self,
            document_summary_request: DocumentSummaryRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentSummaryResponse:
        pass

    @abstractmethod
    async def execute_document_summary_stream(
            self,
            document_summary_request: DocumentSummaryRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[DocumentSummaryStreamEvent]:
        ...
