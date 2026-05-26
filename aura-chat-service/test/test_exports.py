from unittest.mock import MagicMock

from apps.message.exceptions import ExportTooLargeException, MessageAccessDeniedException, MessageNotFoundException
from core.exceptions.base import InsufficientPermissionsException
from test.conftest import make_chat, make_message


EXPORT_VIEW = "apps.message.views.export_view"


def _setup_export_mocks(mocker, messages=None, chat=None):
    """Patches the shared helpers used by all export views."""
    messages = messages or [make_message()]
    chat = chat or make_chat()
    mocker.patch(f"{EXPORT_VIEW}.AccessControl.require_permissions")
    mocker.patch(f"{EXPORT_VIEW}.chat_repository.get_by_id", return_value=chat)
    mocker.patch(f"{EXPORT_VIEW}.membership_repository.is_active_member", return_value=True)
    qs = MagicMock()
    qs.order_by.return_value = messages
    mocker.patch(f"{EXPORT_VIEW}.message_repository.get_messages_by_chat", return_value=qs)
    return chat, messages


# ---------------------------------------------------------------------------
# Chat PDF export  GET /api/v1/chats/{chat_id}/messages/export/pdf/
# ---------------------------------------------------------------------------

def test_export_chat_pdf_returns_200(api_client, mocker):
    _setup_export_mocks(mocker)
    mocker.patch(f"{EXPORT_VIEW}.generate_chat_pdf", return_value=b"%PDF-1.4 fake")
    response = api_client.get("/api/v1/chats/1/messages/export/pdf/")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert "attachment" in response["Content-Disposition"]


def test_export_chat_pdf_permission_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{EXPORT_VIEW}.AccessControl.require_permissions",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/chats/1/messages/export/pdf/")
    assert response.status_code == 403


def test_export_chat_pdf_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{EXPORT_VIEW}.AccessControl.require_permissions")
    mocker.patch(f"{EXPORT_VIEW}.chat_repository.get_by_id", return_value=None)
    response = api_client.get("/api/v1/chats/999/messages/export/pdf/")
    assert response.status_code == 404


def test_export_chat_pdf_not_member_returns_403(api_client, mocker):
    mocker.patch(f"{EXPORT_VIEW}.AccessControl.require_permissions")
    mocker.patch(f"{EXPORT_VIEW}.chat_repository.get_by_id", return_value=make_chat())
    mocker.patch(f"{EXPORT_VIEW}.membership_repository.is_active_member", return_value=False)
    response = api_client.get("/api/v1/chats/1/messages/export/pdf/")
    assert response.status_code == 403


def test_export_chat_pdf_too_large_returns_413(api_client, mocker):
    mocker.patch(f"{EXPORT_VIEW}.AccessControl.require_permissions")
    mocker.patch(f"{EXPORT_VIEW}.chat_repository.get_by_id", return_value=make_chat())
    mocker.patch(f"{EXPORT_VIEW}.membership_repository.is_active_member", return_value=True)
    mocker.patch(
        f"{EXPORT_VIEW}.message_repository.get_messages_by_chat",
        side_effect=ExportTooLargeException(),
    )
    response = api_client.get("/api/v1/chats/1/messages/export/pdf/")
    assert response.status_code == 413


def test_export_chat_pdf_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/chats/1/messages/export/pdf/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Chat Markdown export  GET /api/v1/chats/{chat_id}/messages/export/markdown/
# ---------------------------------------------------------------------------

def test_export_chat_markdown_returns_200(api_client, mocker):
    _setup_export_mocks(mocker)
    mocker.patch(f"{EXPORT_VIEW}.generate_chat_markdown", return_value="# Chat\n\nHello")
    response = api_client.get("/api/v1/chats/1/messages/export/markdown/")
    assert response.status_code == 200
    assert "markdown" in response["Content-Type"]
    assert "attachment" in response["Content-Disposition"]
    assert response["Content-Disposition"].endswith('.md"')


def test_export_chat_markdown_permission_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{EXPORT_VIEW}.AccessControl.require_permissions",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/chats/1/messages/export/markdown/")
    assert response.status_code == 403


def test_export_chat_markdown_too_large_returns_413(api_client, mocker):
    mocker.patch(f"{EXPORT_VIEW}.AccessControl.require_permissions")
    mocker.patch(f"{EXPORT_VIEW}.chat_repository.get_by_id", return_value=make_chat())
    mocker.patch(f"{EXPORT_VIEW}.membership_repository.is_active_member", return_value=True)
    mocker.patch(
        f"{EXPORT_VIEW}.message_repository.get_messages_by_chat",
        side_effect=ExportTooLargeException(),
    )
    response = api_client.get("/api/v1/chats/1/messages/export/markdown/")
    assert response.status_code == 413


# ---------------------------------------------------------------------------
# Chat JSON export  GET /api/v1/chats/{chat_id}/messages/export/json/
# ---------------------------------------------------------------------------

def test_export_chat_json_returns_200(api_client, mocker):
    _setup_export_mocks(mocker)
    mocker.patch(f"{EXPORT_VIEW}.generate_chat_json", return_value='{"messages":[]}')
    response = api_client.get("/api/v1/chats/1/messages/export/json/")
    assert response.status_code == 200
    assert "json" in response["Content-Type"]
    assert "attachment" in response["Content-Disposition"]
    assert response["Content-Disposition"].endswith('.json"')


def test_export_chat_json_permission_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{EXPORT_VIEW}.AccessControl.require_permissions",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/chats/1/messages/export/json/")
    assert response.status_code == 403


def test_export_chat_json_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{EXPORT_VIEW}.AccessControl.require_permissions")
    mocker.patch(f"{EXPORT_VIEW}.chat_repository.get_by_id", return_value=None)
    response = api_client.get("/api/v1/chats/999/messages/export/json/")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# AI responses export  GET /api/v1/chats/{chat_id}/messages/export/ai/
# ---------------------------------------------------------------------------

def test_export_ai_responses_returns_200(api_client, mocker):
    _setup_export_mocks(mocker)
    mocker.patch(f"{EXPORT_VIEW}.generate_ai_responses_markdown", return_value="## AI\nAnswer")
    response = api_client.get("/api/v1/chats/1/messages/export/ai/")
    assert response.status_code == 200
    assert "markdown" in response["Content-Type"]
    assert "_ai.md" in response["Content-Disposition"]


def test_export_ai_responses_permission_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{EXPORT_VIEW}.AccessControl.require_permissions",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/chats/1/messages/export/ai/")
    assert response.status_code == 403


def test_export_ai_responses_too_large_returns_413(api_client, mocker):
    mocker.patch(f"{EXPORT_VIEW}.AccessControl.require_permissions")
    mocker.patch(f"{EXPORT_VIEW}.chat_repository.get_by_id", return_value=make_chat())
    mocker.patch(f"{EXPORT_VIEW}.membership_repository.is_active_member", return_value=True)
    mocker.patch(
        f"{EXPORT_VIEW}.message_repository.get_messages_by_chat",
        side_effect=ExportTooLargeException(),
    )
    response = api_client.get("/api/v1/chats/1/messages/export/ai/")
    assert response.status_code == 413


# ---------------------------------------------------------------------------
# Single message PDF  GET /api/v1/chats/{chat_id}/messages/{message_id}/export/pdf/
# ---------------------------------------------------------------------------

def test_export_message_pdf_returns_200(api_client, mocker):
    chat, _ = _setup_export_mocks(mocker)
    msg = make_message()
    mocker.patch(f"{EXPORT_VIEW}.message_repository.get_by_id_and_chat", return_value=msg)
    mocker.patch(f"{EXPORT_VIEW}.generate_message_pdf", return_value=b"%PDF-1.4 msg")
    response = api_client.get("/api/v1/chats/1/messages/1/export/pdf/")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert "message_1.pdf" in response["Content-Disposition"]


def test_export_message_pdf_not_found_returns_404(api_client, mocker):
    _setup_export_mocks(mocker)
    mocker.patch(f"{EXPORT_VIEW}.message_repository.get_by_id_and_chat", return_value=None)
    response = api_client.get("/api/v1/chats/1/messages/999/export/pdf/")
    assert response.status_code == 404
    assert response.data["error"] == "message_not_found"


def test_export_message_pdf_permission_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{EXPORT_VIEW}.AccessControl.require_permissions",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/chats/1/messages/1/export/pdf/")
    assert response.status_code == 403


def test_export_message_pdf_not_member_returns_403(api_client, mocker):
    mocker.patch(f"{EXPORT_VIEW}.AccessControl.require_permissions")
    mocker.patch(f"{EXPORT_VIEW}.chat_repository.get_by_id", return_value=make_chat())
    mocker.patch(f"{EXPORT_VIEW}.membership_repository.is_active_member", return_value=False)
    response = api_client.get("/api/v1/chats/1/messages/1/export/pdf/")
    assert response.status_code == 403


def test_export_message_pdf_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/chats/1/messages/1/export/pdf/")
    assert response.status_code == 401
