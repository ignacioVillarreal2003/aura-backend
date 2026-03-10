"""
Conversation Controller

Handles CRUD operations for conversations.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status, Header

from app.domain.dtos.conversation import (
    CreateConversationRequest,
    UpdateConversationRequest,
    ConversationResponse,
    ConversationListResponse,
)
# from app.api.dependencies import get_current_user, verify_conversation_ownership
# from app.application.services.conversation_service import ConversationService

router = APIRouter()


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create conversation",
    description="Creates a new conversation for the authenticated user.",
)
async def create_conversation(
    request: CreateConversationRequest,
    # current_user = Depends(get_current_user),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Create a new conversation.
    
    - **title**: Optional title for the conversation
    - **system_prompt**: Optional system prompt to customize assistant behavior
    - **model**: LLM model to use (default: "default")
    - **metadata**: Optional metadata dictionary
    """
    # TODO: Implement conversation creation
    # conversation = await conversation_service.create(request, current_user.id)
    # return ConversationResponse.model_validate(conversation)
    pass


@router.get(
    "",
    response_model=ConversationListResponse,
    summary="List conversations",
    description="Lists conversations for the authenticated user with pagination.",
)
async def list_conversations(
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    status_filter: Optional[str] = Query(
        None, 
        alias="status",
        pattern="^(active|archived)$",
        description="Filter by status"
    ),
    search: Optional[str] = Query(None, max_length=100, description="Search in title"),
    sort: str = Query("created_at", pattern="^(created_at|updated_at|title)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    # current_user = Depends(get_current_user),
):
    """
    List conversations with pagination and filtering.
    
    Supports cursor-based pagination for efficient scrolling through large lists.
    """
    # TODO: Implement conversation listing
    pass


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation",
    description="Gets details of a specific conversation.",
)
async def get_conversation(
    conversation_id: UUID,
    # conversation = Depends(verify_conversation_ownership),
):
    """
    Get conversation details.
    
    Returns full conversation information including system prompt and metadata.
    """
    # TODO: Implement get conversation
    # return ConversationResponse.model_validate(conversation)
    pass


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Update conversation",
    description="Updates a conversation's title, system_prompt, status, or metadata.",
)
async def update_conversation(
    conversation_id: UUID,
    request: UpdateConversationRequest,
    # conversation = Depends(verify_conversation_ownership),
):
    """
    Update conversation properties.
    
    - **title**: New title
    - **system_prompt**: New system prompt
    - **status**: New status (active/archived)
    - **metadata**: Metadata to merge with existing
    """
    # TODO: Implement conversation update
    pass


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation",
    description="Soft-deletes a conversation.",
)
async def delete_conversation(
    conversation_id: UUID,
    # conversation = Depends(verify_conversation_ownership),
):
    """
    Delete a conversation (soft delete).
    
    The conversation and its messages are marked as deleted but not removed from the database.
    """
    # TODO: Implement conversation deletion
    pass


