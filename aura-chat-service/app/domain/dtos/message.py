from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ==================== Tool Definitions ====================

class FunctionDefinition(BaseModel):
    """Definition of a function that can be called by the LLM."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    parameters: Optional[dict] = None


class ToolDefinition(BaseModel):
    """Definition of a tool available to the LLM."""
    type: str = Field("function", pattern="^function$")
    function: FunctionDefinition


# ==================== Attachment References ====================

class AttachmentRef(BaseModel):
    """Reference to an uploaded attachment."""
    file_id: UUID
    type: str = Field(..., pattern="^(image|file|audio|video)$")


class AttachmentResponse(BaseModel):
    """Response body for an attachment."""
    id: UUID
    file_name: str
    file_type: str
    mime_type: str
    file_size: int
    url: Optional[str] = None
    description: Optional[str] = None
    metadata: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== Tool Call ====================

class FunctionCall(BaseModel):
    """Function call details."""
    name: str
    arguments: str  # JSON string


class ToolCallResponse(BaseModel):
    """Response body for a tool call."""
    id: str
    type: str
    function: FunctionCall


class ToolCallResultRequest(BaseModel):
    """Request body for submitting a tool call result."""
    result: str = Field(..., max_length=100000)
    is_error: bool = False

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "result": '{"temperature": 22, "condition": "sunny"}',
                "is_error": False
            }
        }
    )


# ==================== Request DTOs ====================

class SendMessageRequest(BaseModel):
    """Request body for sending a message."""
    content: str = Field(..., min_length=1, max_length=100000)
    role: str = Field("user", pattern="^(user|system)$")
    attachments: Optional[list[AttachmentRef]] = Field(None, max_length=10)
    tools: Optional[list[ToolDefinition]] = Field(None, max_length=50)
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": "¿Cómo funciona la fotosíntesis?",
                "role": "user"
            }
        }
    )


# ==================== Response DTOs ====================

class UsageInfo(BaseModel):
    """Token usage information."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class MessageResponse(BaseModel):
    """Response body for a message."""
    id: UUID
    role: str
    content: Optional[str]
    status: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    model_used: Optional[str] = None
    finish_reason: Optional[str] = None
    tool_call_id: Optional[str] = None
    sequence_number: int
    attachments: list[AttachmentResponse] = []
    tool_calls: list[ToolCallResponse] = []
    metadata: dict = {}
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationInfo(BaseModel):
    """Brief conversation info for message responses."""
    id: UUID
    message_count: int
    total_tokens: int


class SendMessageResponse(BaseModel):
    """Response body after sending a message."""
    user_message: MessageResponse
    assistant_message: MessageResponse
    conversation: ConversationInfo


class ToolCallResultResponse(BaseModel):
    """Response body after submitting a tool call result."""
    tool_message: MessageResponse
    assistant_message: MessageResponse


# ==================== Pagination ====================

class PaginationInfo(BaseModel):
    """Pagination metadata."""
    next_cursor: Optional[str] = None
    has_more: bool
    total_count: Optional[int] = None


class MessageListResponse(BaseModel):
    """Response body for listing messages."""
    data: list[MessageResponse]
    pagination: PaginationInfo


# ==================== SSE Events ====================

class SSEMessageStart(BaseModel):
    """SSE event: message_start"""
    message_id: str
    conversation_id: str


class SSEContentDelta(BaseModel):
    """SSE event: content_delta"""
    delta: str


class SSEToolCallStart(BaseModel):
    """SSE event: tool_call_start"""
    tool_call: ToolCallResponse


class SSEToolCallDelta(BaseModel):
    """SSE event: tool_call_delta"""
    tool_call_id: str
    arguments_delta: str


class SSEMessageComplete(BaseModel):
    """SSE event: message_complete"""
    message_id: str
    finish_reason: Optional[str]
    usage: Optional[UsageInfo]


class SSEError(BaseModel):
    """SSE event: error"""
    message: str
    code: str


