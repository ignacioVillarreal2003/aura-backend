from typing import Optional
from fastapi import APIRouter, Query, status, Header

from app.domain.dtos.conversation import (
    CreateChatRequest,
    UpdateChatRequest,
    ChatResponse,
    ChatListResponse,
)

router = APIRouter()


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create chat",
    description="Creates a new chat. If member_ids is empty, creates an individual chat (solo el creador). If member_ids has values, creates a group chat.",
)
async def create_chat(
    request: CreateChatRequest,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    # TODO: Implement
    # - Create chat record
    # - Add creator as member (status=active)
    # - Add request.member_ids as members (status=active)
    # - Return ChatResponse with chat_type derived from membership count
    pass


@router.get(
    "",
    response_model=ChatListResponse,
    summary="List chats",
    description="Lists chats the authenticated user belongs to, with pagination.",
)
async def list_chats(
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100),
    chat_type: Optional[str] = Query(None, pattern="^(individual|group)$", description="Filter by chat type"),
    search: Optional[str] = Query(None, max_length=100, description="Search in chat name"),
    sort: str = Query("created_at", pattern="^(created_at|updated_at|name|last_message_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    # TODO: Implement
    # - Query chats where user is a member (via chat_membership)
    # - Filter by chat_type: individual = membership count == 1, group = membership count > 1
    pass


@router.get(
    "/{chat_id}",
    response_model=ChatResponse,
    summary="Get chat",
    description="Gets details of a specific chat, including all members.",
)
async def get_chat(chat_id: int):
    # TODO: Implement
    # - Verify user is a member of this chat
    # - Return ChatResponse with members list
    pass


@router.patch(
    "/{chat_id}",
    response_model=ChatResponse,
    summary="Update chat",
    description="Updates a chat's name, system_prompt or response_style.",
)
async def update_chat(chat_id: int, request: UpdateChatRequest):
    # TODO: Implement
    # - Verify user is a member (or admin) of this chat
    # - Update fields
    pass


@router.delete(
    "/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete chat",
    description="Soft-deletes a chat and all its messages.",
)
async def delete_chat(chat_id: int):
    # TODO: Implement
    # - Verify user is a member of this chat
    # - Soft-delete: set deleted_at and deleted_by
    pass
