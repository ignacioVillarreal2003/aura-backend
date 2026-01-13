from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ==================== Request DTOs ====================

class CreateConversationRequest(BaseModel):
    """Request body for creating a new conversation."""
    title: Optional[str] = Field(None, max_length=255)
    system_prompt: Optional[str] = Field(None, max_length=10000)
    model: str = Field("default", max_length=100)
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Consulta sobre Python",
                "system_prompt": "Eres un experto en Python.",
                "model": "llama3",
                "metadata": {"tags": ["trabajo"]}
            }
        }
    )


class UpdateConversationRequest(BaseModel):
    """Request body for updating a conversation."""
    title: Optional[str] = Field(None, max_length=255)
    system_prompt: Optional[str] = Field(None, max_length=10000)
    status: Optional[str] = Field(None, pattern="^(active|archived)$")
    metadata: Optional[dict] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Nuevo título",
                "status": "archived"
            }
        }
    )


# ==================== Response DTOs ====================

class ConversationResponse(BaseModel):
    """Response body for a conversation."""
    id: UUID
    title: Optional[str]
    system_prompt: Optional[str]
    model: str
    status: str
    metadata: dict
    message_count: int
    total_tokens: int
    created_at: datetime
    updated_at: Optional[datetime]
    last_message_preview: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationSummary(BaseModel):
    """Summary of a conversation for list views."""
    id: UUID
    title: Optional[str]
    model: str
    status: str
    message_count: int
    total_tokens: int
    created_at: datetime
    updated_at: Optional[datetime]
    last_message_preview: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ==================== Pagination ====================

class PaginationInfo(BaseModel):
    """Pagination metadata."""
    next_cursor: Optional[str] = None
    has_more: bool
    total_count: Optional[int] = None


class ConversationListResponse(BaseModel):
    """Response body for listing conversations."""
    data: list[ConversationSummary]
    pagination: PaginationInfo

