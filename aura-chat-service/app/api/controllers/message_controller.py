from typing import Optional
from fastapi import APIRouter, Query, status, Header
from fastapi.responses import StreamingResponse

from app.domain.dtos.message import (
    SendMessageRequest,
    ChatMessageResponse,
    ChatMessageListResponse,
)

router = APIRouter()


@router.post(
    "/chats/{chat_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send message (non-streaming)",
    description="Sends a message in a chat and returns the complete LLM response.",
)
async def send_message(
    chat_id: int,
    request: SendMessageRequest,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    # TODO: Implement
    # - Verify user is a member of this chat
    # - Save user message (sender_type=user) to chat_message
    # - Call LLM service with chat history
    # - Save LLM response (sender_type=system) to chat_message
    # - Update chat.last_message_at
    # - Return the LLM response message
    pass


@router.post(
    "/chats/{chat_id}/messages/stream",
    summary="Send message (streaming)",
    description="Sends a message in a chat and streams the LLM response via SSE.",
    responses={
        200: {
            "description": "SSE stream of response chunks",
            "content": {"text/event-stream": {}}
        }
    }
)
async def send_message_stream(
    chat_id: int,
    request: SendMessageRequest,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    # TODO: Implement
    # - Verify user is a member of this chat
    # - Save user message to chat_message
    # - Stream LLM response via SSE:
    #     event: message_start  → message_id, chat_id
    #     event: content_delta  → delta (chunk de texto)
    #     event: message_complete → finish_reason
    #     event: error          → si algo falla
    #     event: done           → [DONE]
    # - Once stream finishes, save full response to chat_message
    # - Update chat.last_message_at
    pass


@router.get(
    "/chats/{chat_id}/messages",
    response_model=ChatMessageListResponse,
    summary="List messages",
    description="Lists messages in a chat ordered by creation time (oldest first by default).",
)
async def list_messages(
    chat_id: int,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(50, ge=1, le=200),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    include_deleted: bool = Query(False),
):
    # TODO: Implement
    # - Verify user is a member of this chat
    # - Query chat_message filtered by chat_id
    # - Apply pagination and ordering
    pass


@router.get(
    "/chats/{chat_id}/messages/{message_id}",
    response_model=ChatMessageResponse,
    summary="Get message",
    description="Gets a specific message from a chat.",
)
async def get_message(chat_id: int, message_id: int):
    # TODO: Implement
    # - Verify user is a member of this chat
    # - Return the message
    pass


@router.delete(
    "/chats/{chat_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete message",
    description="Soft-deletes a message.",
)
async def delete_message(chat_id: int, message_id: int):
    # TODO: Implement
    # - Verify user is a member of this chat
    # - Soft-delete: set deleted_at and deleted_by
    pass
