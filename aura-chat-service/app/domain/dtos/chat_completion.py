from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.domain.dtos.message import ToolDefinition, ToolCallResponse, UsageInfo


# ==================== OpenAI-Compatible Chat Completion ====================

class ChatMessage(BaseModel):
    """A message in the chat completion request/response."""
    role: str = Field(..., pattern="^(system|user|assistant|tool)$")
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCallResponse]] = None
    tool_call_id: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role": "user",
                "content": "¿Qué es Python?"
            }
        }
    )


class ChatCompletionRequest(BaseModel):
    """Request body for chat completion (OpenAI-compatible)."""
    model: str = Field(..., max_length=100)
    messages: list[ChatMessage] = Field(..., min_length=1)
    stream: bool = False
    temperature: Optional[float] = Field(None, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, ge=1)
    tools: Optional[list[ToolDefinition]] = None
    conversation_id: Optional[UUID] = None  # Aura extension

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "model": "llama3",
                "messages": [
                    {"role": "system", "content": "Eres un asistente útil."},
                    {"role": "user", "content": "¿Qué es Python?"}
                ],
                "stream": False,
                "temperature": 0.7
            }
        }
    )


class ChatCompletionChoice(BaseModel):
    """A choice in the chat completion response."""
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    """Response body for chat completion (OpenAI-compatible)."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: Optional[UsageInfo] = None
    conversation_id: Optional[UUID] = None  # Aura extension

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "chatcmpl-abc123",
                "object": "chat.completion",
                "created": 1736765400,
                "model": "llama3",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Python es un lenguaje de programación..."
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 30,
                    "completion_tokens": 150,
                    "total_tokens": 180
                }
            }
        }
    )


# ==================== Streaming Chunks ====================

class ChatCompletionChunkDelta(BaseModel):
    """Delta content in a streaming chunk."""
    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[list[dict]] = None


class ChatCompletionChunkChoice(BaseModel):
    """A choice in a streaming chunk."""
    index: int
    delta: ChatCompletionChunkDelta
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """A streaming chunk (OpenAI-compatible)."""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionChunkChoice]


