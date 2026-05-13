from apps.message.exceptions import MessageAccessDeniedException, MessageNotFoundException
from test.conftest import make_thread_reply


THREAD_VIEW = "apps.message.views.thread_view"


# ---------------------------------------------------------------------------
# List thread replies  GET /api/v1/chats/{chat_id}/messages/{message_id}/thread/
# ---------------------------------------------------------------------------

def test_list_thread_replies_returns_200(api_client, mocker):
    mocker.patch(
        f"{THREAD_VIEW}.thread_service.get_thread",
        return_value=[make_thread_reply(), make_thread_reply(reply_id=2)],
    )
    response = api_client.get("/api/v1/chats/1/messages/1/thread/")
    assert response.status_code == 200
    assert len(response.data) == 2


def test_list_thread_replies_empty_returns_200(api_client, mocker):
    mocker.patch(
        f"{THREAD_VIEW}.thread_service.get_thread",
        return_value=[],
    )
    response = api_client.get("/api/v1/chats/1/messages/1/thread/")
    assert response.status_code == 200
    assert response.data == []


def test_list_thread_replies_message_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{THREAD_VIEW}.thread_service.get_thread",
        side_effect=MessageNotFoundException(),
    )
    response = api_client.get("/api/v1/chats/1/messages/999/thread/")
    assert response.status_code == 404
    assert response.data["error"] == "message_not_found"


def test_list_thread_replies_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{THREAD_VIEW}.thread_service.get_thread",
        side_effect=MessageAccessDeniedException(),
    )
    response = api_client.get("/api/v1/chats/1/messages/1/thread/")
    assert response.status_code == 403


def test_list_thread_replies_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/chats/1/messages/1/thread/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Add thread reply  POST /api/v1/chats/{chat_id}/messages/{message_id}/thread/
# ---------------------------------------------------------------------------

def test_add_thread_reply_returns_201(api_client, mocker):
    mocker.patch(
        f"{THREAD_VIEW}.thread_service.add_reply",
        return_value=make_thread_reply(),
    )
    response = api_client.post(
        "/api/v1/chats/1/messages/1/thread/",
        {"message": "A reply"},
        format="json",
    )
    assert response.status_code == 201
    assert "id" in response.data


def test_add_thread_reply_empty_message_returns_400(api_client, mocker):
    mocker.patch(f"{THREAD_VIEW}.thread_service.add_reply")
    response = api_client.post(
        "/api/v1/chats/1/messages/1/thread/",
        {"message": ""},
        format="json",
    )
    assert response.status_code == 400


def test_add_thread_reply_missing_message_returns_400(api_client, mocker):
    mocker.patch(f"{THREAD_VIEW}.thread_service.add_reply")
    response = api_client.post(
        "/api/v1/chats/1/messages/1/thread/",
        {},
        format="json",
    )
    assert response.status_code == 400


def test_add_thread_reply_too_long_returns_400(api_client, mocker):
    mocker.patch(f"{THREAD_VIEW}.thread_service.add_reply")
    response = api_client.post(
        "/api/v1/chats/1/messages/1/thread/",
        {"message": "x" * 5001},
        format="json",
    )
    assert response.status_code == 400


def test_add_thread_reply_passes_text_to_service(api_client, mocker):
    svc = mocker.patch(
        f"{THREAD_VIEW}.thread_service.add_reply",
        return_value=make_thread_reply(),
    )
    api_client.post(
        "/api/v1/chats/1/messages/1/thread/",
        {"message": "My reply"},
        format="json",
    )
    svc.assert_called_once()
    assert svc.call_args[1]["message_text"] == "My reply"


def test_add_thread_reply_message_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{THREAD_VIEW}.thread_service.add_reply",
        side_effect=MessageNotFoundException(),
    )
    response = api_client.post(
        "/api/v1/chats/1/messages/999/thread/",
        {"message": "Reply"},
        format="json",
    )
    assert response.status_code == 404


def test_add_thread_reply_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{THREAD_VIEW}.thread_service.add_reply",
        side_effect=MessageAccessDeniedException(),
    )
    response = api_client.post(
        "/api/v1/chats/1/messages/1/thread/",
        {"message": "Reply"},
        format="json",
    )
    assert response.status_code == 403


def test_add_thread_reply_unauthenticated(anon_client):
    response = anon_client.post(
        "/api/v1/chats/1/messages/1/thread/",
        {"message": "Reply"},
        format="json",
    )
    assert response.status_code == 401
