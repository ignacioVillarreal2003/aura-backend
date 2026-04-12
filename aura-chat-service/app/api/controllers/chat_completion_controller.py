"""
Chat Completion Controller

OpenAI-compatible chat completion endpoint.
"""

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from app.domain.dtos.chat_completion import (
    ChatCompletionRequest,
    ChatCompletionResponse,
)
# from app.api.dependencies import get_current_user
# from app.application.services.chat_completion_service import ChatCompletionService

router = APIRouter()


@router.post(
    "/completions",
    response_model=ChatCompletionResponse,
    summary="Chat completion (OpenAI-compatible)",
    description="Generate a chat completion using the OpenAI-compatible API format.",
    responses={
        200: {
            "description": "Chat completion response",
            "content": {
                "application/json": {
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
                },
                "text/event-stream": {
                    "example": "data: {\"id\":\"chatcmpl-abc123\",\"object\":\"chat.completion.chunk\",...}\n\n"
                }
            }
        }
    }
)
async def chat_completion(
    request: ChatCompletionRequest,
    # current_user = Depends(get_current_user),
):
    """
    Generate a chat completion.
    
    This endpoint is compatible with the OpenAI Chat Completions API format,
    making it easy to integrate with existing tools and libraries.
    
    **Aura Extensions:**
    - `conversation_id`: Associate the completion with an existing conversation
    
    **Streaming:**
    When `stream=true`, returns Server-Sent Events with chunks in OpenAI format:
    ```
    data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1736765400,"model":"llama3","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}
    
    data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1736765400,"model":"llama3","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}
    
    data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1736765400,"model":"llama3","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}
    
    data: [DONE]
    ```
    """
    # TODO: Implement chat completion
    # if request.stream:
    #     async def generate():
    #         async for chunk in chat_service.generate_stream(request, current_user.id):
    #             yield f"data: {chunk.model_dump_json()}\n\n"
    #         yield "data: [DONE]\n\n"
    #     
    #     return StreamingResponse(
    #         generate(),
    #         media_type="text/event-stream",
    #         headers={
    #             "Cache-Control": "no-cache",
    #             "Connection": "keep-alive",
    #             "X-Accel-Buffering": "no"
    #         }
    #     )
    # 
    # return await chat_service.generate(request, current_user.id)
    pass


