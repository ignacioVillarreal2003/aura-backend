from typing import Optional

from fastapi import APIRouter, Query, status, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.conversation import (
    CreateChatRequest,
    UpdateChatRequest,
    ChatResponse,
    ChatListResponse,
)
from app.infrastructure.database import get_db
from app.infrastructure.auth_deps import get_current_user_id
from app.application.services.chat_service import ChatService

router = APIRouter()


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create chat",
    description="Creates a new chat. Empty member_ids = individual chat (creator only).",
)
async def create_chat(
    request: CreateChatRequest,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    session: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await ChatService(session).create_chat(request, user_id)


@router.get(
    "",
    response_model=ChatListResponse,
    summary="List chats",
    description="Lists chats the authenticated user belongs to.",
)
async def list_chats(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await ChatService(session).list_chats(user_id, limit=limit)


@router.get(
    "/{chat_id}",
    response_model=ChatResponse,
    summary="Get chat",
)
async def get_chat(
    chat_id: int,
    session: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await ChatService(session).get_chat(chat_id, user_id)


@router.patch(
    "/{chat_id}",
    response_model=ChatResponse,
    summary="Update chat",
)
async def update_chat(
    chat_id: int,
    request: UpdateChatRequest,
    session: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await ChatService(session).update_chat(chat_id, request, user_id)


@router.delete(
    "/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete chat",
)
async def delete_chat(
    chat_id: int,
    session: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    await ChatService(session).delete_chat(chat_id, user_id)
