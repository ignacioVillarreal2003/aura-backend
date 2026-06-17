from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.general_chat.general_chat_request import GeneralChatRequest
from app.domain.dtos.user_interactions.general_chat.general_chat_response import GeneralChatResponse
from app.domain.dtos.user_interactions.general_chat.general_chat_stream_events import GeneralChatStreamEvent


class GeneralChatServiceInterface(ABC):
    @abstractmethod
    async def execute_general_chat(
            self,
            general_chat_request: GeneralChatRequest,
            authenticated_user: AuthenticatedUser,
    ) -> GeneralChatResponse:
        pass

    @abstractmethod
    async def execute_general_chat_stream(
            self,
            general_chat_request: GeneralChatRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[GeneralChatStreamEvent]:
        pass
