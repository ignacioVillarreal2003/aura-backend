from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from apps.message.exceptions import (
    ChatAiReplyInProgressException,
    MessageAccessDeniedException,
    MessageDeleteForbiddenException,
    MessageNotFoundException,
    NoMessageToRegenerateException,
    NotChatOwnerException,
    ReaderCannotSendMessageException,
)
from test.conftest import make_chat, make_message, mock_cursor_pagination


MSG_VIEW = "apps.message.views.message_view"


def _setup_send_message_mocks(mocker, chat=None, msg=None, turn=None, acquired=True):
    chat = chat or make_chat()
    msg = msg or make_message()
    turn = turn or SimpleNamespace(question="Q", answer="A", fragments=[])

    mocker.patch(f"{MSG_VIEW}.chat_repository.get_by_id", return_value=chat)
    mocker.patch(f"{MSG_VIEW}.try_acquire", return_value=acquired)
    mocker.patch(f"{MSG_VIEW}.release")
    mocker.patch(f"{MSG_VIEW}.broadcast_chat_ai_lock_change")
    mocker.patch(f"{MSG_VIEW}.message_service.send_message", return_value=msg)
    mock_run = mocker.patch(
        f"{MSG_VIEW}.message_service.run_document_question",
        new_callable=AsyncMock,
        return_value=turn,
    )
    return msg, mock_run


# ---------------------------------------------------------------------------
# List messages  GET /api/v1/chats/{chat_id}/messages/
# ---------------------------------------------------------------------------

def test_list_messages_returns_200(api_client, mocker):
    mocker.patch(
        f"{MSG_VIEW}.message_service.get_messages",
        return_value=MagicMock_qs(mocker),
    )
    mock_cursor_pagination(mocker, MSG_VIEW, items=[make_message()])
    response = api_client.get("/api/v1/chats/1/messages/")
    assert response.status_code == 200
    assert "results" in response.data


def MagicMock_qs(mocker):
    from unittest.mock import MagicMock
    qs = MagicMock()
    qs.filter.return_value = qs
    qs.order_by.return_value = qs
    return qs


def test_list_messages_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{MSG_VIEW}.message_service.get_messages",
        side_effect=MessageAccessDeniedException(),
    )
    response = api_client.get("/api/v1/chats/1/messages/")
    assert response.status_code == 403
    assert response.data["error"] == "message_access_denied"


def test_list_messages_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/chats/1/messages/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Send message  POST /api/v1/chats/{chat_id}/messages/
# ---------------------------------------------------------------------------

def test_send_message_returns_201(api_client, mocker):
    msg, _ = _setup_send_message_mocks(mocker)
    response = api_client.post(
        "/api/v1/chats/1/messages/",
        {"message": "Hello!"},
        format="json",
    )
    assert response.status_code == 201
    assert "message" in response.data
    assert "assistant" in response.data
    assert "assistant_error" in response.data


def test_send_message_calls_service_with_text(api_client, mocker):
    msg, _ = _setup_send_message_mocks(mocker)
    svc = mocker.patch(f"{MSG_VIEW}.message_service.send_message", return_value=msg)
    api_client.post("/api/v1/chats/1/messages/", {"message": "Hello!"}, format="json")
    svc.assert_called_once()
    assert svc.call_args.kwargs["text"] == "Hello!"


def test_send_message_empty_body_returns_400(api_client, mocker):
    _setup_send_message_mocks(mocker)
    response = api_client.post("/api/v1/chats/1/messages/", {}, format="json")
    assert response.status_code == 400


def test_send_message_too_long_returns_400(api_client, mocker):
    _setup_send_message_mocks(mocker)
    response = api_client.post(
        "/api/v1/chats/1/messages/",
        {"message": "x" * 10001},
        format="json",
    )
    assert response.status_code == 400


def test_send_message_both_text_and_audio_returns_400(api_client, mocker):
    _setup_send_message_mocks(mocker)
    from io import BytesIO
    audio = BytesIO(b"fake audio")
    audio.name = "test.wav"
    response = api_client.post(
        "/api/v1/chats/1/messages/",
        {"message": "Hello", "audio": audio},
        format="multipart",
    )
    assert response.status_code == 400


def test_send_message_ai_in_progress_returns_409(api_client, mocker):
    _setup_send_message_mocks(mocker, acquired=False)
    response = api_client.post(
        "/api/v1/chats/1/messages/",
        {"message": "Hello!"},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["error"] == "chat_ai_reply_in_progress"


def test_send_message_reader_forbidden_returns_403(api_client, mocker):
    mocker.patch(f"{MSG_VIEW}.chat_repository.get_by_id", return_value=make_chat())
    mocker.patch(f"{MSG_VIEW}.try_acquire", return_value=True)
    mocker.patch(f"{MSG_VIEW}.release")
    mocker.patch(f"{MSG_VIEW}.broadcast_chat_ai_lock_change")
    mocker.patch(
        f"{MSG_VIEW}.message_service.send_message",
        side_effect=ReaderCannotSendMessageException(),
    )
    response = api_client.post(
        "/api/v1/chats/1/messages/",
        {"message": "Hello!"},
        format="json",
    )
    assert response.status_code == 403
    assert response.data["error"] == "reader_cannot_send_message"


def test_send_message_unauthenticated(anon_client):
    response = anon_client.post(
        "/api/v1/chats/1/messages/",
        {"message": "Hello!"},
        format="json",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Delete message  DELETE /api/v1/chats/{chat_id}/messages/{message_id}/
# ---------------------------------------------------------------------------

def test_delete_message_returns_204(api_client, mocker):
    mocker.patch("apps.message.views.message_delete_view.message_service.delete_message")
    response = api_client.delete("/api/v1/chats/1/messages/1/")
    assert response.status_code == 204


def test_delete_message_not_found_returns_404(api_client, mocker):
    mocker.patch(
        "apps.message.views.message_delete_view.message_service.delete_message",
        side_effect=MessageNotFoundException(),
    )
    response = api_client.delete("/api/v1/chats/1/messages/999/")
    assert response.status_code == 404
    assert response.data["error"] == "message_not_found"


def test_delete_message_forbidden_returns_403(api_client, mocker):
    mocker.patch(
        "apps.message.views.message_delete_view.message_service.delete_message",
        side_effect=MessageDeleteForbiddenException(),
    )
    response = api_client.delete("/api/v1/chats/1/messages/1/")
    assert response.status_code == 403
    assert response.data["error"] == "message_delete_forbidden"


# ---------------------------------------------------------------------------
# Clear history  DELETE /api/v1/chats/{chat_id}/messages/clear/
# ---------------------------------------------------------------------------

def test_clear_history_returns_204(api_client, mocker):
    mocker.patch("apps.message.views.clear_view.message_service.clear_history")
    response = api_client.delete("/api/v1/chats/1/messages/clear/")
    assert response.status_code == 204


def test_clear_history_not_owner_returns_403(api_client, mocker):
    mocker.patch(
        "apps.message.views.clear_view.message_service.clear_history",
        side_effect=NotChatOwnerException(),
    )
    response = api_client.delete("/api/v1/chats/1/messages/clear/")
    assert response.status_code == 403
    assert response.data["error"] == "not_chat_owner"


def test_clear_history_chat_not_found_returns_404(api_client, mocker):
    from apps.chat.exceptions import ChatNotFoundException
    mocker.patch(
        "apps.message.views.clear_view.message_service.clear_history",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.delete("/api/v1/chats/1/messages/clear/")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Mark as read  POST /api/v1/chats/{chat_id}/messages/read/
# ---------------------------------------------------------------------------

def test_mark_as_read_returns_204(api_client, mocker):
    mocker.patch(
        "apps.message.views.mark_read_view.membership_repository.is_active_member",
        return_value=True,
    )
    mocker.patch("apps.message.views.mark_read_view.membership_repository.mark_as_read")
    response = api_client.post("/api/v1/chats/1/messages/read/")
    assert response.status_code == 204


def test_mark_as_read_not_member_returns_403(api_client, mocker):
    mocker.patch(
        "apps.message.views.mark_read_view.membership_repository.is_active_member",
        return_value=False,
    )
    mocker.patch("apps.message.views.mark_read_view.membership_repository.mark_as_read")
    response = api_client.post("/api/v1/chats/1/messages/read/")
    assert response.status_code == 403
    assert response.data["error"] == "message_access_denied"


def test_mark_as_read_unauthenticated(anon_client):
    response = anon_client.post("/api/v1/chats/1/messages/read/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Regenerate  POST /api/v1/chats/{chat_id}/messages/regenerate/
# ---------------------------------------------------------------------------

REGEN_VIEW = "apps.message.views.regenerate_view"


def test_regenerate_returns_200_with_assistant(api_client, mocker):
    turn = SimpleNamespace(question="Q?", answer="A!", fragments=[])
    mocker.patch(f"{REGEN_VIEW}.try_acquire", return_value=True)
    mocker.patch(f"{REGEN_VIEW}.release")
    mocker.patch(f"{REGEN_VIEW}.broadcast_chat_ai_lock_change")
    mocker.patch(f"{REGEN_VIEW}.message_service.delete_last_ai_message")
    mocker.patch(
        f"{REGEN_VIEW}.message_service.run_document_question",
        new_callable=AsyncMock,
        return_value=turn,
    )
    response = api_client.post("/api/v1/chats/1/messages/regenerate/")
    assert response.status_code == 200
    assert response.data["assistant"]["question"] == "Q?"
    assert response.data["assistant"]["answer"] == "A!"
    assert response.data["assistant_error"] is None


def test_regenerate_ai_in_progress_returns_409(api_client, mocker):
    mocker.patch(f"{REGEN_VIEW}.try_acquire", return_value=False)
    response = api_client.post("/api/v1/chats/1/messages/regenerate/")
    assert response.status_code == 409
    assert response.data["error"] == "chat_ai_reply_in_progress"


def test_regenerate_no_message_to_regen_returns_409(api_client, mocker):
    mocker.patch(f"{REGEN_VIEW}.try_acquire", return_value=True)
    mocker.patch(f"{REGEN_VIEW}.release")
    mocker.patch(f"{REGEN_VIEW}.broadcast_chat_ai_lock_change")
    mocker.patch(
        f"{REGEN_VIEW}.message_service.delete_last_ai_message",
        side_effect=NoMessageToRegenerateException(),
    )
    response = api_client.post("/api/v1/chats/1/messages/regenerate/")
    assert response.status_code == 409
    assert response.data["error"] == "no_message_to_regenerate"
