from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.conversation import Chat
from app.domain.models.chat_membership import ChatMembership, MembershipStatus


class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        name: str,
        created_by: int,
        system_prompt: Optional[str] = None,
        response_style: Optional[str] = None,
    ) -> Chat:
        chat = Chat(
            name=name,
            system_prompt=system_prompt,
            response_style=response_style,
            created_by=created_by,
        )
        self.session.add(chat)
        await self.session.flush()
        return chat

    async def get_by_id(self, chat_id: int) -> Optional[Chat]:
        result = await self.session.execute(
            select(Chat)
            .where(and_(Chat.id == chat_id, Chat.deleted_at.is_(None)))
            .options(selectinload(Chat.memberships), selectinload(Chat.messages))
        )
        return result.scalar_one_or_none()

    async def get_chats_by_member(self, member_id: int, limit: int = 20) -> list[Chat]:
        result = await self.session.execute(
            select(Chat)
            .join(ChatMembership, ChatMembership.chat_id == Chat.id)
            .where(
                and_(
                    ChatMembership.member_id == member_id,
                    ChatMembership.deleted_at.is_(None),
                    Chat.deleted_at.is_(None),
                )
            )
            .order_by(Chat.created_at.desc())
            .limit(limit)
            .options(selectinload(Chat.memberships), selectinload(Chat.messages))
        )
        return list(result.scalars().unique().all())

    async def update(
        self,
        chat: Chat,
        name: Optional[str],
        system_prompt: Optional[str],
        response_style: Optional[str],
        updated_by: int,
    ) -> Chat:
        if name is not None:
            chat.name = name
        if system_prompt is not None:
            chat.system_prompt = system_prompt
        if response_style is not None:
            chat.response_style = response_style
        chat.updated_by = updated_by
        chat.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return chat

    async def soft_delete(self, chat: Chat, deleted_by: int) -> None:
        chat.soft_delete(deleted_by)
        await self.session.flush()

    async def create_membership(self, chat_id: int, member_id: int, created_by: int) -> ChatMembership:
        membership = ChatMembership(
            chat_id=chat_id,
            member_id=member_id,
            status=MembershipStatus.active,
            joined_at=datetime.now(timezone.utc),
            created_by=created_by,
        )
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def get_membership(self, chat_id: int, member_id: int) -> Optional[ChatMembership]:
        result = await self.session.execute(
            select(ChatMembership).where(
                and_(
                    ChatMembership.chat_id == chat_id,
                    ChatMembership.member_id == member_id,
                    ChatMembership.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def update_last_message_at(self, chat: Chat) -> None:
        chat.last_message_at = datetime.now(timezone.utc)
        await self.session.flush()
