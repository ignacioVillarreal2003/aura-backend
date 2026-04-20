from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.chat import Chat


class ChatRepositoryInterface(ABC):
    @abstractmethod
    async def get_chat_by_id(
            self,
            chat_id: int,
            database_session: AsyncSession,
    ) -> Chat | None:
        pass
