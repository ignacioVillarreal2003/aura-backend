"""
Fixtures compartidas para los tests del aura-chat-service.

Estrategia:
- Se parchean ChatService y MessageService para evitar conexiones reales a la BD.
- Se sobreescriben las dependencias get_db y get_current_user_id de FastAPI.
- Todos los tests son síncronos usando TestClient de Starlette.
"""

import os
import sys

sys.path.insert(
    0,
    os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "aura-chat-service")
    ),
)

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.infrastructure.database import get_db
from app.infrastructure.auth_deps import get_current_user_id
from app.domain.dtos.conversation import (
    ChatListResponse,
    ChatMembershipResponse,
    ChatResponse,
    ChatSummary,
    PaginationInfo,
)
from app.domain.dtos.message import (
    ChatMessageListResponse,
    ChatMessageResponse,
    PaginationInfo as MsgPaginationInfo,
)

USER_ID = 1
NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers para construir respuestas de prueba
# ---------------------------------------------------------------------------

def make_chat_response(
    chat_id: int = 1,
    name: str = "Chat de prueba",
    chat_type: str = "individual",
) -> ChatResponse:
    return ChatResponse(
        id=chat_id,
        name=name,
        system_prompt=None,
        response_style=None,
        chat_type=chat_type,
        last_message_at=None,
        members=[
            ChatMembershipResponse(
                id=1, member_id=USER_ID, status="active", joined_at=NOW
            )
        ],
        created_by=USER_ID,
        created_at=NOW,
        updated_at=None,
    )


def make_chat_list_response(chats=None) -> ChatListResponse:
    if chats is None:
        chats = [
            ChatSummary(
                id=1,
                name="Chat de prueba",
                chat_type="individual",
                member_count=1,
                last_message_at=None,
                created_at=NOW,
                updated_at=None,
            )
        ]
    return ChatListResponse(data=chats, pagination=PaginationInfo(has_more=False))


def make_message_response(
    msg_id: int = 1,
    chat_id: int = 1,
    message: str = "Respuesta del asistente.",
) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=msg_id,
        chat_id=chat_id,
        message=message,
        sender_type="system",
        created_by=None,
        created_at=NOW,
        deleted_at=None,
    )


def make_message_list_response(messages=None) -> ChatMessageListResponse:
    if messages is None:
        messages = [make_message_response()]
    return ChatMessageListResponse(
        data=messages,
        pagination=MsgPaginationInfo(has_more=False),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_chat_service():
    with patch("app.api.controllers.conversation_controller.ChatService") as MockClass:
        instance = AsyncMock()
        MockClass.return_value = instance
        yield instance


@pytest.fixture
def mock_message_service():
    with patch("app.api.controllers.message_controller.MessageService") as MockClass:
        instance = AsyncMock()
        MockClass.return_value = instance
        yield instance


@pytest.fixture
def client(mock_chat_service, mock_message_service):
    async def _mock_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _mock_db
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
