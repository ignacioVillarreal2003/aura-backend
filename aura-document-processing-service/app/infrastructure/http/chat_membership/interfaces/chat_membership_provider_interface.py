from abc import ABC, abstractmethod

from app.infrastructure.http.chat_membership.dtos.chat_membership_response import (
    ChatMembershipResponse,
)


class ChatMembershipProviderInterface(ABC):
    @abstractmethod
    async def get_membership(
            self,
            *,
            chat_id: int,
            user_id: int,
            authorization_header: str | None,
    ) -> ChatMembershipResponse:
        pass
