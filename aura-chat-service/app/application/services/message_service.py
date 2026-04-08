from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.message import ChatMessageResponse, ChatMessageListResponse, PaginationInfo
from app.domain.models.message import ChatMessage, SenderType
from app.infrastructure.repositories.chat_repository import ChatRepository
from app.infrastructure.repositories.message_repository import MessageRepository
from app.infrastructure.llm_client import LLMClient, llm_client as _default_llm_client
from app.application.exceptions.api_exceptions import NotFoundError, ForbiddenError


def _to_response(msg: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=msg.id,
        chat_id=msg.chat_id,
        message=msg.message,
        sender_type=msg.sender_type.value,
        created_by=msg.created_by,
        created_at=msg.created_at,
        deleted_at=msg.deleted_at,
    )


class MessageService:
    def __init__(self, session: AsyncSession, llm: Optional[LLMClient] = None):
        self.chat_repo = ChatRepository(session)
        self.msg_repo = MessageRepository(session)
        self.llm = llm or _default_llm_client

    async def send_message(
        self, chat_id: int, message: str, user_id: int, token: str
    ) -> ChatMessageResponse:
        """
        Persist user message → build history → call LLM → persist assistant reply.
        If the LLM call fails the whole request is rolled back by get_db().
        """
        chat = await self.chat_repo.get_by_id(chat_id)
        if not chat:
            raise NotFoundError(f"Chat {chat_id} not found")
        if not await self.chat_repo.get_membership(chat_id, user_id):
            raise ForbiddenError()

        # Persist the user's message
        await self.msg_repo.create(chat_id, message, SenderType.user, user_id)

        # Load full history (includes the message we just flushed)
        history = await self.msg_repo.get_by_chat(chat_id)

        # Map to the LLM contract: user → "human", system (assistant) → "assistant"
        llm_messages = [
            {
                "role": "human" if msg.sender_type == SenderType.user else "assistant",
                "content": msg.message,
            }
            for msg in history
        ]

        # Call aura-llm-service /api/agent
        llm_reply = await self.llm.call_agent(llm_messages, token)

        # Persist the assistant's response (sender_type=system, no created_by)
        assistant_msg = await self.msg_repo.create(chat_id, llm_reply, SenderType.system, None)

        await self.chat_repo.update_last_message_at(chat)

        return _to_response(assistant_msg)

    async def list_messages(
        self,
        chat_id: int,
        user_id: int,
        limit: int = 50,
        include_deleted: bool = False,
    ) -> ChatMessageListResponse:
        if not await self.chat_repo.get_membership(chat_id, user_id):
            raise ForbiddenError()
        messages = await self.msg_repo.get_by_chat(chat_id, limit=limit, include_deleted=include_deleted)
        return ChatMessageListResponse(
            data=[_to_response(m) for m in messages],
            pagination=PaginationInfo(has_more=False),
        )

    async def get_message(self, chat_id: int, message_id: int, user_id: int) -> ChatMessageResponse:
        if not await self.chat_repo.get_membership(chat_id, user_id):
            raise ForbiddenError()
        msg = await self.msg_repo.get_by_id(message_id, chat_id)
        if not msg:
            raise NotFoundError(f"Message {message_id} not found")
        return _to_response(msg)

    async def delete_message(self, chat_id: int, message_id: int, user_id: int) -> None:
        if not await self.chat_repo.get_membership(chat_id, user_id):
            raise ForbiddenError()
        msg = await self.msg_repo.get_by_id(message_id, chat_id)
        if not msg:
            raise NotFoundError(f"Message {message_id} not found")
        await self.msg_repo.soft_delete(msg, user_id)
