from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.message import ChatMessage, SenderType


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        chat_id: int,
        message: str,
        sender_type: SenderType,
        created_by: Optional[int],
    ) -> ChatMessage:
        msg = ChatMessage(
            chat_id=chat_id,
            message=message,
            sender_type=sender_type,
            created_by=created_by,
        )
        self.session.add(msg)
        await self.session.flush()
        await self.session.refresh(msg)
        return msg

    async def get_by_id(self, message_id: int, chat_id: Optional[int] = None) -> Optional[ChatMessage]:
        conditions = [ChatMessage.id == message_id, ChatMessage.deleted_at.is_(None)]
        if chat_id is not None:
            conditions.append(ChatMessage.chat_id == chat_id)
        result = await self.session.execute(select(ChatMessage).where(and_(*conditions)))
        return result.scalar_one_or_none()

    async def get_by_chat(
        self, chat_id: int, limit: int = 100, include_deleted: bool = False
    ) -> list[ChatMessage]:
        conditions = [ChatMessage.chat_id == chat_id]
        if not include_deleted:
            conditions.append(ChatMessage.deleted_at.is_(None))
        result = await self.session.execute(
            select(ChatMessage)
            .where(and_(*conditions))
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def soft_delete(self, msg: ChatMessage, deleted_by: int) -> None:
        msg.soft_delete(deleted_by)
        await self.session.flush()
