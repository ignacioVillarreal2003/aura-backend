from fastapi import APIRouter

from app.api.controllers.conversation_controller import router as conversation_router
from app.api.controllers.message_controller import router as message_router
from app.api.controllers.chat_completion_controller import router as chat_completion_router
from app.api.controllers.tool_call_controller import router as tool_call_router

router = APIRouter()

# Include all routers
router.include_router(conversation_router, prefix="/conversations", tags=["Conversations"])
router.include_router(message_router, tags=["Messages"])
router.include_router(chat_completion_router, prefix="/chat", tags=["Chat Completions"])
router.include_router(tool_call_router, prefix="/tool-calls", tags=["Tool Calls"])

