"""
Tool Call Controller

Handles tool/function call results.
"""

from fastapi import APIRouter, Query, status
from fastapi.responses import StreamingResponse

from app.domain.dtos.message import (
    ToolCallResultRequest,
    ToolCallResultResponse,
)
# from app.api.dependencies import get_current_user
# from app.application.services.tool_call_service import ToolCallService

router = APIRouter()


@router.post(
    "/{tool_call_id}/result",
    response_model=ToolCallResultResponse,
    summary="Submit tool call result",
    description="Submits the result of a tool call to continue the conversation.",
)
async def submit_tool_call_result(
    tool_call_id: str,
    request: ToolCallResultRequest,
    stream: bool = Query(False, description="Use streaming for assistant response"),
    # current_user = Depends(get_current_user),
):
    """
    Submit the result of a tool call.
    
    When the assistant requests a tool call (function calling), the client
    executes the function and submits the result here. The service will:
    
    1. Create a message with role="tool" containing the result
    2. Send the updated conversation to the LLM
    3. Return the assistant's response
    
    **Parameters:**
    - **tool_call_id**: The ID of the tool call (from the assistant's response)
    - **result**: The result of executing the tool (JSON string recommended)
    - **is_error**: Set to true if the tool execution failed
    
    **Example flow:**
    1. User asks: "What's the weather in Buenos Aires?"
    2. Assistant responds with tool_call: `get_weather(location="Buenos Aires")`
    3. Client executes `get_weather` and gets: `{"temp": 22, "condition": "sunny"}`
    4. Client POSTs to this endpoint with the result
    5. Assistant responds: "The weather in Buenos Aires is sunny with 22°C"
    """
    # TODO: Implement tool call result submission
    # if stream:
    #     async def generate():
    #         async for chunk in tool_call_service.submit_result_stream(
    #             tool_call_id, request, current_user.id
    #         ):
    #             yield f"event: {chunk.event}\ndata: {chunk.data}\n\n"
    #         yield "event: done\ndata: [DONE]\n\n"
    #     
    #     return StreamingResponse(
    #         generate(),
    #         media_type="text/event-stream"
    #     )
    # 
    # return await tool_call_service.submit_result(tool_call_id, request, current_user.id)
    pass


