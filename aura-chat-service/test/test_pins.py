from apps.chat.exceptions import ChatNotFoundException
from apps.message.exceptions import MessageAccessDeniedException, MessageNotFoundException, NotChatOwnerException
from test.conftest import make_pin


PIN_VIEW = "apps.message.views.pin_view"


# ---------------------------------------------------------------------------
# List pinned  GET /api/v1/chats/{chat_id}/messages/pinned/
# ---------------------------------------------------------------------------

def test_list_pinned_returns_200(api_client, mocker):
    mocker.patch(
        f"{PIN_VIEW}.pinned_message_service.list_pinned",
        return_value=[make_pin()],
    )
    response = api_client.get("/api/v1/chats/1/messages/pinned/")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1


def test_list_pinned_empty_returns_200(api_client, mocker):
    mocker.patch(
        f"{PIN_VIEW}.pinned_message_service.list_pinned",
        return_value=[],
    )
    response = api_client.get("/api/v1/chats/1/messages/pinned/")
    assert response.status_code == 200
    assert response.data["results"] == []


def test_list_pinned_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{PIN_VIEW}.pinned_message_service.list_pinned",
        side_effect=MessageAccessDeniedException(),
    )
    response = api_client.get("/api/v1/chats/1/messages/pinned/")
    assert response.status_code == 403
    assert response.data["error"] == "message_access_denied"


def test_list_pinned_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{PIN_VIEW}.pinned_message_service.list_pinned",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.get("/api/v1/chats/999/messages/pinned/")
    assert response.status_code == 404


def test_list_pinned_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/chats/1/messages/pinned/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Pin message  POST /api/v1/chats/{chat_id}/messages/{message_id}/pin/
# ---------------------------------------------------------------------------

def test_pin_message_returns_201(api_client, mocker):
    mocker.patch(
        f"{PIN_VIEW}.pinned_message_service.pin_message",
        return_value=make_pin(),
    )
    response = api_client.post("/api/v1/chats/1/messages/1/pin/")
    assert response.status_code == 201
    assert "id" in response.data


def test_pin_message_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{PIN_VIEW}.pinned_message_service.pin_message",
        side_effect=MessageNotFoundException(),
    )
    response = api_client.post("/api/v1/chats/1/messages/999/pin/")
    assert response.status_code == 404
    assert response.data["error"] == "message_not_found"


def test_pin_message_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{PIN_VIEW}.pinned_message_service.pin_message",
        side_effect=MessageAccessDeniedException(),
    )
    response = api_client.post("/api/v1/chats/1/messages/1/pin/")
    assert response.status_code == 403


def test_pin_message_unauthenticated(anon_client):
    response = anon_client.post("/api/v1/chats/1/messages/1/pin/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Unpin message  DELETE /api/v1/chats/{chat_id}/messages/{message_id}/pin/
# ---------------------------------------------------------------------------

def test_unpin_message_returns_204(api_client, mocker):
    mocker.patch(f"{PIN_VIEW}.pinned_message_service.unpin_message")
    response = api_client.delete("/api/v1/chats/1/messages/1/pin/")
    assert response.status_code == 204


def test_unpin_message_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{PIN_VIEW}.pinned_message_service.unpin_message",
        side_effect=MessageNotFoundException(),
    )
    response = api_client.delete("/api/v1/chats/1/messages/999/pin/")
    assert response.status_code == 404


def test_unpin_message_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{PIN_VIEW}.pinned_message_service.unpin_message",
        side_effect=MessageAccessDeniedException(),
    )
    response = api_client.delete("/api/v1/chats/1/messages/1/pin/")
    assert response.status_code == 403


def test_unpin_message_unauthenticated(anon_client):
    response = anon_client.delete("/api/v1/chats/1/messages/1/pin/")
    assert response.status_code == 401


def test_pin_message_not_owner_returns_403(api_client, mocker):
    mocker.patch(
        f"{PIN_VIEW}.pinned_message_service.pin_message",
        side_effect=NotChatOwnerException(),
    )
    response = api_client.post("/api/v1/chats/1/messages/1/pin/")
    assert response.status_code == 403
    assert response.data["error"] == "not_chat_owner"


def test_unpin_message_not_owner_returns_403(api_client, mocker):
    mocker.patch(
        f"{PIN_VIEW}.pinned_message_service.unpin_message",
        side_effect=NotChatOwnerException(),
    )
    response = api_client.delete("/api/v1/chats/1/messages/1/pin/")
    assert response.status_code == 403
    assert response.data["error"] == "not_chat_owner"
