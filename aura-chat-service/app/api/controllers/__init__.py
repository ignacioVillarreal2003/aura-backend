from fastapi import APIRouter

from app.api.controllers.conversation_controller import router as chat_router
from app.api.controllers.message_controller import router as message_router

router = APIRouter()

router.include_router(chat_router, prefix="/chats", tags=["Chats"])
router.include_router(message_router, tags=["Messages"])
