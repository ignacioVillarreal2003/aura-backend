import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError

from app.configuration.environment_variables import settings
from app.infrastructure.database import _session_factory
from app.application.services.message_service import MessageService
from app.application.exceptions.api_exceptions import NotFoundError, ForbiddenError, LLMError

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_user_id(token: Optional[str]) -> int:
    """Decode JWT and return user_id, falling back to 1 for dev tokens."""
    if not token:
        return 1
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        raw = payload.get("user_id") or payload.get("sub")
        return int(raw) if raw else 1
    except (JWTError, ValueError, TypeError):
        return 1


@router.websocket("/ws/chats/{chat_id}")
async def websocket_chat(
    websocket: WebSocket,
    chat_id: int,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time chat.

    Connect: ws://host/api/v1/ws/chats/{chat_id}?token=<bearer_token>

    Client sends:  {"message": "user text"}
    Server sends:
      - {"type": "message", "data": {id, chat_id, message, sender_type, created_by, created_at}}
      - {"type": "error", "code": "...", "message": "..."}
    """
    await websocket.accept()
    user_id = _extract_user_id(token)
    bearer_token = token or "user_token_123"

    logger.info("WebSocket connected: chat_id=%s user_id=%s", chat_id, user_id)

    try:
        while True:
            data = await websocket.receive_json()
            message_text = (data.get("message") or "").strip()

            if not message_text:
                await websocket.send_json({"type": "error", "code": "EMPTY_MESSAGE", "message": "Message cannot be empty"})
                continue

            try:
                async with _session_factory() as session:
                    try:
                        svc = MessageService(session)
                        response = await svc.send_message(chat_id, message_text, user_id, bearer_token)
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        raise

                await websocket.send_json({
                    "type": "message",
                    "data": {
                        "id": response.id,
                        "chat_id": response.chat_id,
                        "message": response.message,
                        "sender_type": response.sender_type,
                        "created_by": response.created_by,
                        "created_at": response.created_at.isoformat(),
                    },
                })
            except ForbiddenError:
                await websocket.send_json({"type": "error", "code": "FORBIDDEN", "message": "Access denied to this chat"})
            except NotFoundError as e:
                await websocket.send_json({"type": "error", "code": "NOT_FOUND", "message": str(e)})
            except LLMError as e:
                await websocket.send_json({"type": "error", "code": "LLM_ERROR", "message": str(e)})
            except Exception:
                logger.exception("Error processing message: chat_id=%s", chat_id)
                await websocket.send_json({"type": "error", "code": "INTERNAL_ERROR", "message": "An unexpected error occurred"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: chat_id=%s user_id=%s", chat_id, user_id)
    except Exception:
        logger.exception("Fatal WebSocket error: chat_id=%s", chat_id)
        await websocket.close(code=4500)
