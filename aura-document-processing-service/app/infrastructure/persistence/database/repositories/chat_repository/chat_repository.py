import logging
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.database.orm.chat import Chat
from app.infrastructure.persistence.database.repositories.chat_repository.chat_repository_interface import (
    ChatRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.database_exceptions import DatabaseException

logger = logging.getLogger(__name__)


class ChatRepository(ChatRepositoryInterface):
    async def get_chat_by_id(
            self,
            chat_id: int,
            database_session: AsyncSession,
    ) -> Chat | None:
        try:
            result = await database_session.execute(
                select(Chat).where(
                    Chat.id == chat_id,
                    Chat.deleted_at.is_(None),
                )
            )
            return result.scalars().first()
        except SQLAlchemyError as e:
            logger.exception(
                "Failed to fetch the chat.",
                extra={"chat_id": chat_id},
            )
            raise DatabaseException("Failed to fetch the chat.") from e
