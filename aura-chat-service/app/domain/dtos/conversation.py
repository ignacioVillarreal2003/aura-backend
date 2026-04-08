from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


# ==================== Request DTOs ====================

class CreateChatRequest(BaseModel):
    """
    Request body for creating a new chat.

    - Individual chat: no member_ids (solo el creador como miembro).
    - Group chat: member_ids con los IDs de los otros participantes.
    """
    name: str = Field(..., min_length=1, max_length=255)
    system_prompt: Optional[str] = Field(None, max_length=10000)
    response_style: Optional[str] = Field(None, max_length=10000)
    member_ids: list[int] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Mi chat con el asistente",
                "system_prompt": "Eres un asistente útil.",
                "member_ids": []
            }
        }
    )


class UpdateChatRequest(BaseModel):
    """Request body for updating a chat."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    system_prompt: Optional[str] = Field(None, max_length=10000)
    response_style: Optional[str] = Field(None, max_length=10000)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Nuevo nombre del chat",
                "response_style": "Responde siempre de forma concisa."
            }
        }
    )


# ==================== Response DTOs ====================

class ChatMembershipResponse(BaseModel):
    """Membership info within a chat response."""
    id: int
    member_id: int
    status: str
    joined_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    """Response body for a chat."""
    id: int
    name: str
    system_prompt: Optional[str]
    response_style: Optional[str]
    chat_type: Literal["individual", "group"]
    last_message_at: Optional[datetime]
    members: list[ChatMembershipResponse]
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ChatSummary(BaseModel):
    """Summary of a chat for list views."""
    id: int
    name: str
    chat_type: Literal["individual", "group"]
    member_count: int
    last_message_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# ==================== Pagination ====================

class PaginationInfo(BaseModel):
    """Pagination metadata."""
    next_cursor: Optional[str] = None
    has_more: bool
    total_count: Optional[int] = None


class ChatListResponse(BaseModel):
    """Response body for listing chats."""
    data: list[ChatSummary]
    pagination: PaginationInfo
