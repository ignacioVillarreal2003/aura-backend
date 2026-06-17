from abc import ABC, abstractmethod
from starlette.responses import StreamingResponse

from app.application.services.user_interactions.general_chat_service.interfaces.general_chat_service_interface import (
    GeneralChatServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.general_chat.general_chat_request import GeneralChatRequest
from app.domain.dtos.user_interactions.general_chat.general_chat_response import GeneralChatResponse


class GeneralChatControllerInterface(ABC):
    @abstractmethod
    async def execute_general_chat(
            self,
            general_chat_request: GeneralChatRequest,
            general_chat_service: GeneralChatServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> GeneralChatResponse:
        pass

    @abstractmethod
    async def execute_general_chat_stream(
            self,
            general_chat_request: GeneralChatRequest,
            general_chat_service: GeneralChatServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> StreamingResponse:
        pass
