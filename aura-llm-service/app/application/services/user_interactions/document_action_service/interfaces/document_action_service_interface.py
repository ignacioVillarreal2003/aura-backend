from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.user_interactions.document_action.document_action_response import DocumentActionResponse
from app.domain.dtos.user_interactions.document_action.document_action_stream_events import DocumentActionStreamEvent


class DocumentActionServiceInterface(ABC):
    @abstractmethod
    async def execute_document_action(
            self,
            document_action_request: DocumentActionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentActionResponse:
        pass

    @abstractmethod
    async def execute_document_action_stream(
            self,
            document_action_request: DocumentActionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[DocumentActionStreamEvent]:
        pass
