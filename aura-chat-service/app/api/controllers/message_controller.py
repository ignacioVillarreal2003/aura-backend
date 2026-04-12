from typing import Optional

from fastapi import APIRouter, Query, status, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.message import (
    SendMessageRequest,
    ChatMessageResponse,
    ChatMessageListResponse,
)
from app.infrastructure.database import get_db
from app.infrastructure.auth_deps import get_current_user_id, get_bearer_token
from app.application.services.message_service import MessageService

router = APIRouter()


@router.post(
    "/chats/{chat_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send message",
    description="Sends a user message and returns the LLM assistant reply.",
)
async def send_message(
    chat_id: int,
    request: SendMessageRequest,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    session: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    token: str = Depends(get_bearer_token),
):
    return await MessageService(session).send_message(chat_id, request.message, user_id, token)


@router.get(
    "/chats/{chat_id}/messages",
    response_model=ChatMessageListResponse,
    summary="List messages",
    description="Lists messages in a chat ordered by creation time (oldest first).",
)
async def list_messages(
    chat_id: int,
    limit: int = Query(50, ge=1, le=200),
    include_deleted: bool = Query(False),
    session: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await MessageService(session).list_messages(
        chat_id, user_id, limit=limit, include_deleted=include_deleted
    )


@router.get(
    "/chats/{chat_id}/messages/{message_id}",
    response_model=ChatMessageResponse,
    summary="Get message",
)
async def get_message(
    chat_id: int,
    message_id: int,
    session: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await MessageService(session).get_message(chat_id, message_id, user_id)


@router.delete(
    "/chats/{chat_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete message",
)
async def delete_message(
    chat_id: int,
    message_id: int,
    session: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    await MessageService(session).delete_message(chat_id, message_id, user_id)
