from abc import ABC, abstractmethod

from app.application.services.document_action_service.interfaces.document_action_service_interface import (
    DocumentActionServiceInterface,
)
from app.domain.dtos.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.document_action.document_action_response import DocumentActionResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentActionControllerInterface(ABC):
    @abstractmethod
    async def execute_document_action(
            self,
            document_action_request: DocumentActionRequest,
            document_action_service: DocumentActionServiceInterface,
            authenticated_user: AuthenticationResponse,
    ) -> DocumentActionResponse:
        pass
