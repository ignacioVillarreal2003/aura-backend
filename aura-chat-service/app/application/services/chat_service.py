from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.conversation import (
    CreateChatRequest,
    UpdateChatRequest,
    ChatResponse,
    ChatSummary,
    ChatListResponse,
    ChatMembershipResponse,
    PaginationInfo,
)
from app.domain.models.conversation import Chat
from app.infrastructure.repositories.chat_repository import ChatRepository
from app.application.exceptions.api_exceptions import NotFoundError, ForbiddenError


def _to_response(chat: Chat) -> ChatResponse:
    active = [m for m in chat.memberships if m.deleted_at is None]
    return ChatResponse(
        id=chat.id,
        name=chat.name,
        system_prompt=chat.system_prompt,
        response_style=chat.response_style,
        chat_type="individual" if len(active) <= 1 else "group",
        last_message_at=chat.last_message_at,
        members=[
            ChatMembershipResponse(
                id=m.id,
                member_id=m.member_id,
                status=m.status.value,
                joined_at=m.joined_at,
            )
            for m in active
        ],
        created_by=chat.created_by,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


class ChatService:
    def __init__(self, session: AsyncSession):
        self.repo = ChatRepository(session)

    async def create_chat(self, request: CreateChatRequest, user_id: int) -> ChatResponse:
        chat = await self.repo.create(
            request.name, user_id, request.system_prompt, request.response_style
        )
        await self.repo.create_membership(chat.id, user_id, user_id)
        for mid in request.member_ids:
            if mid != user_id:
                await self.repo.create_membership(chat.id, mid, user_id)
        chat = await self.repo.get_by_id(chat.id)
        return _to_response(chat)

    async def list_chats(self, user_id: int, limit: int = 20) -> ChatListResponse:
        chats = await self.repo.get_chats_by_member(user_id, limit=limit)
        summaries = [
            ChatSummary(
                id=c.id,
                name=c.name,
                chat_type="individual"
                if len([m for m in c.memberships if m.deleted_at is None]) <= 1
                else "group",
                member_count=len([m for m in c.memberships if m.deleted_at is None]),
                last_message_at=c.last_message_at,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in chats
        ]
        return ChatListResponse(data=summaries, pagination=PaginationInfo(has_more=False))

    async def get_chat(self, chat_id: int, user_id: int) -> ChatResponse:
        chat = await self.repo.get_by_id(chat_id)
        if not chat:
            raise NotFoundError(f"Chat {chat_id} not found")
        if not await self.repo.get_membership(chat_id, user_id):
            raise ForbiddenError()
        return _to_response(chat)

    async def update_chat(self, chat_id: int, request: UpdateChatRequest, user_id: int) -> ChatResponse:
        chat = await self.repo.get_by_id(chat_id)
        if not chat:
            raise NotFoundError(f"Chat {chat_id} not found")
        if not await self.repo.get_membership(chat_id, user_id):
            raise ForbiddenError()
        await self.repo.update(chat, request.name, request.system_prompt, request.response_style, user_id)
        chat = await self.repo.get_by_id(chat_id)
        return _to_response(chat)

    async def delete_chat(self, chat_id: int, user_id: int) -> None:
        chat = await self.repo.get_by_id(chat_id)
        if not chat:
            raise NotFoundError(f"Chat {chat_id} not found")
        if not await self.repo.get_membership(chat_id, user_id):
            raise ForbiddenError()
        await self.repo.soft_delete(chat, user_id)
