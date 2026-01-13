"""
Message Controller

Handles message operations within conversations.
Supports both streaming (SSE) and non-streaming responses.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status, Header
from fastapi.responses import StreamingResponse

from app.domain.dtos.message import (
    SendMessageRequest,
    SendMessageResponse,
    MessageResponse,
    MessageListResponse,
)
# from app.api.dependencies import get_current_user, verify_conversation_ownership
# from app.application.services.message_service import MessageService

router = APIRouter()


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
    summary="Send message (non-streaming)",
    description="Sends a message and receives the complete assistant response.",
)
async def send_message(
    conversation_id: UUID,
    request: SendMessageRequest,
    # conversation = Depends(verify_conversation_ownership),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Send a message and get the assistant's response.
    
    The response is returned after the LLM has finished generating.
    For real-time streaming, use the /stream endpoint instead.
    
    - **content**: Message content
    - **role**: Message role (user/system)
    - **attachments**: Optional file attachments
    - **tools**: Optional tool definitions for function calling
    """
    # TODO: Implement message sending
    pass


@router.post(
    "/conversations/{conversation_id}/messages/stream",
    summary="Send message (streaming)",
    description="Sends a message and streams the assistant response via SSE.",
    responses={
        200: {
            "description": "SSE stream of response chunks",
            "content": {"text/event-stream": {}}
        }
    }
)
async def send_message_stream(
    conversation_id: UUID,
    request: SendMessageRequest,
    # conversation = Depends(verify_conversation_ownership),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Send a message and stream the assistant's response.
    
    Returns a Server-Sent Events (SSE) stream with the following events:
    
    - **message_start**: Initial event with message and conversation IDs
    - **content_delta**: Text chunks as they are generated
    - **tool_call_start**: When a tool call begins
    - **tool_call_delta**: Tool call argument chunks
    - **message_complete**: Final event with usage statistics
    - **error**: If an error occurs during generation
    - **done**: Stream termination signal
    
    Example client code (JavaScript):
    ```javascript
    const eventSource = new EventSource('/api/v1/conversations/{id}/messages/stream');
    eventSource.addEventListener('content_delta', (e) => {
        const data = JSON.parse(e.data);
        console.log(data.delta);
    });
    ```
    """
    # TODO: Implement streaming response
    # async def generate():
    #     async for chunk in message_service.generate_stream(conversation, request):
    #         yield f"event: {chunk.event}\ndata: {chunk.data}\n\n"
    #     yield "event: done\ndata: [DONE]\n\n"
    # 
    # return StreamingResponse(
    #     generate(),
    #     media_type="text/event-stream",
    #     headers={
    #         "Cache-Control": "no-cache",
    #         "Connection": "keep-alive",
    #         "X-Accel-Buffering": "no"
    #     }
    # )
    pass


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
    summary="List messages",
    description="Lists messages in a conversation with pagination.",
)
async def list_messages(
    conversation_id: UUID,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(50, ge=1, le=200, description="Results per page"),
    order: str = Query("asc", pattern="^(asc|desc)$", description="Sort order"),
    include_deleted: bool = Query(False, description="Include deleted messages"),
    # conversation = Depends(verify_conversation_ownership),
):
    """
    List messages in a conversation.
    
    Messages are returned in chronological order by default (oldest first).
    Use order=desc for reverse chronological order.
    """
    # TODO: Implement message listing
    pass


@router.get(
    "/conversations/{conversation_id}/messages/{message_id}",
    response_model=MessageResponse,
    summary="Get message",
    description="Gets details of a specific message.",
)
async def get_message(
    conversation_id: UUID,
    message_id: UUID,
    # conversation = Depends(verify_conversation_ownership),
):
    """
    Get message details.
    
    Returns full message information including attachments and tool calls.
    """
    # TODO: Implement get message
    pass


@router.delete(
    "/conversations/{conversation_id}/messages/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete message",
    description="Soft-deletes a specific message.",
)
async def delete_message(
    conversation_id: UUID,
    message_id: UUID,
    # conversation = Depends(verify_conversation_ownership),
):
    """
    Delete a message (soft delete).
    
    Note: Deleting a user message will also delete subsequent assistant responses.
    """
    # TODO: Implement message deletion
    pass


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/regenerate",
    response_model=MessageResponse,
    summary="Regenerate response",
    description="Regenerates the assistant's response for a message.",
)
async def regenerate_message(
    conversation_id: UUID,
    message_id: UUID,
    stream: bool = Query(False, description="Use streaming for response"),
    # conversation = Depends(verify_conversation_ownership),
):
    """
    Regenerate the assistant's response.
    
    Deletes the existing assistant response and generates a new one.
    The message_id should be the user message to regenerate from.
    """
    # TODO: Implement message regeneration
    pass

