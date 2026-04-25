from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.database.orm.chat import Chat


class ChatRepositoryInterface(ABC):
    @abstractmethod
    async def get_chat_by_id(
            self,
            chat_id: int,
            database_session: AsyncSession,
    ) -> Chat | None:
        pass
