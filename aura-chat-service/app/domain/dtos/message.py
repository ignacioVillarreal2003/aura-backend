from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


# ==================== Request DTOs ====================

class SendMessageRequest(BaseModel):
    """Request body for sending a message in a chat."""
    message: str = Field(..., min_length=1, max_length=100000)
    sender_type: str = Field("user", pattern="^(user|system)$")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "¿Cómo funciona la fotosíntesis?",
                "sender_type": "user"
            }
        }
    )


# ==================== Response DTOs ====================

class ChatMessageResponse(BaseModel):
    """Response body for a chat message."""
    id: int
    chat_id: int
    message: str
    sender_type: str
    created_by: Optional[int]
    created_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ==================== Pagination ====================

class PaginationInfo(BaseModel):
    """Pagination metadata."""
    next_cursor: Optional[str] = None
    has_more: bool
    total_count: Optional[int] = None


class ChatMessageListResponse(BaseModel):
    """Response body for listing messages in a chat."""
    data: list[ChatMessageResponse]
    pagination: PaginationInfo


# ==================== SSE Events ====================

class SSEMessageStart(BaseModel):
    """SSE event: message_start — se emite al iniciar la generación."""
    message_id: str
    chat_id: str


class SSEContentDelta(BaseModel):
    """SSE event: content_delta — chunk de texto generado por el LLM."""
    delta: str


class SSEMessageComplete(BaseModel):
    """SSE event: message_complete — se emite al finalizar la generación."""
    message_id: str
    finish_reason: Optional[str]


class SSEError(BaseModel):
    """SSE event: error — si ocurre un error durante la generación."""
    message: str
    code: str
