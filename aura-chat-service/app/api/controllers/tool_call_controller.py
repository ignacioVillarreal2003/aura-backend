from fastapi import APIRouter

router = APIRouter()

# Tool calls are handled by the LLM service directly.
# This router is reserved for future use if tool call results
# need to be submitted back to continue a chat flow.
