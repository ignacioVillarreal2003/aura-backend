from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.document.document_action.document_action_response import DocumentActionResponse


class DocumentActionServiceInterface(ABC):
    @abstractmethod
    async def execute_document_action(
            self,
            document_action_request: DocumentActionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentActionResponse:
        pass
