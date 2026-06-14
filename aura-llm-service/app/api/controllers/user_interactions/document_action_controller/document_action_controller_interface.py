from abc import ABC, abstractmethod
from starlette.responses import StreamingResponse

from app.application.services.user_interactions.document_action_service.interfaces.document_action_service_interface import (
    DocumentActionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.user_interactions.document_action.document_action_response import DocumentActionResponse


class DocumentActionControllerInterface(ABC):
    @abstractmethod
    async def execute_document_action(
            self,
            document_action_request: DocumentActionRequest,
            document_action_service: DocumentActionServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentActionResponse:
        pass

    @abstractmethod
    async def execute_document_action_stream(
            self,
            document_action_request: DocumentActionRequest,
            document_action_service: DocumentActionServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> StreamingResponse:
        pass
