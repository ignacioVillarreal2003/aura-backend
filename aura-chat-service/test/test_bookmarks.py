from apps.chat.exceptions import ChatNotFoundException
from apps.message.exceptions import MessageAccessDeniedException, MessageNotFoundException
from test.conftest import make_message, mock_cursor_pagination


BOOKMARK_VIEW = "apps.message.views.bookmark_view"


# ---------------------------------------------------------------------------
# Bookmark  POST /api/v1/chats/{chat_id}/messages/{message_id}/bookmark/
# ---------------------------------------------------------------------------

def test_bookmark_message_returns_204(api_client, mocker):
    mocker.patch(f"{BOOKMARK_VIEW}.bookmark_service.bookmark")
    response = api_client.post("/api/v1/chats/1/messages/1/bookmark/")
    assert response.status_code == 204


def test_bookmark_message_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{BOOKMARK_VIEW}.bookmark_service.bookmark",
        side_effect=MessageNotFoundException(),
    )
    response = api_client.post("/api/v1/chats/1/messages/999/bookmark/")
    assert response.status_code == 404
    assert response.data["error"] == "message_not_found"


def test_bookmark_message_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{BOOKMARK_VIEW}.bookmark_service.bookmark",
        side_effect=MessageAccessDeniedException(),
    )
    response = api_client.post("/api/v1/chats/1/messages/1/bookmark/")
    assert response.status_code == 403
    assert response.data["error"] == "message_access_denied"


def test_bookmark_message_unauthenticated(anon_client):
    response = anon_client.post("/api/v1/chats/1/messages/1/bookmark/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Unbookmark  DELETE /api/v1/chats/{chat_id}/messages/{message_id}/bookmark/
# ---------------------------------------------------------------------------

def test_unbookmark_message_returns_204(api_client, mocker):
    mocker.patch(f"{BOOKMARK_VIEW}.bookmark_service.unbookmark")
    response = api_client.delete("/api/v1/chats/1/messages/1/bookmark/")
    assert response.status_code == 204


def test_unbookmark_message_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{BOOKMARK_VIEW}.bookmark_service.unbookmark",
        side_effect=MessageNotFoundException(),
    )
    response = api_client.delete("/api/v1/chats/1/messages/999/bookmark/")
    assert response.status_code == 404


def test_unbookmark_message_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{BOOKMARK_VIEW}.bookmark_service.unbookmark",
        side_effect=MessageAccessDeniedException(),
    )
    response = api_client.delete("/api/v1/chats/1/messages/1/bookmark/")
    assert response.status_code == 403


def test_unbookmark_message_unauthenticated(anon_client):
    response = anon_client.delete("/api/v1/chats/1/messages/1/bookmark/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# List bookmarked  GET /api/v1/chats/{chat_id}/messages/bookmarked/
# ---------------------------------------------------------------------------

def test_list_bookmarked_returns_200(api_client, mocker):
    from unittest.mock import MagicMock
    qs = MagicMock()
    qs.filter.return_value = qs
    qs.order_by.return_value = qs
    mocker.patch(
        f"{BOOKMARK_VIEW}.bookmark_service.list_bookmarked",
        return_value=qs,
    )
    mock_cursor_pagination(mocker, BOOKMARK_VIEW, items=[make_message()])
    response = api_client.get("/api/v1/chats/1/messages/bookmarked/")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1


def test_list_bookmarked_empty_returns_200(api_client, mocker):
    from unittest.mock import MagicMock
    qs = MagicMock()
    qs.filter.return_value = qs
    qs.order_by.return_value = qs
    mocker.patch(
        f"{BOOKMARK_VIEW}.bookmark_service.list_bookmarked",
        return_value=qs,
    )
    mock_cursor_pagination(mocker, BOOKMARK_VIEW, items=[])
    response = api_client.get("/api/v1/chats/1/messages/bookmarked/")
    assert response.status_code == 200
    assert response.data["results"] == []


def test_list_bookmarked_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{BOOKMARK_VIEW}.bookmark_service.list_bookmarked",
        side_effect=MessageAccessDeniedException(),
    )
    response = api_client.get("/api/v1/chats/1/messages/bookmarked/")
    assert response.status_code == 403


def test_list_bookmarked_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{BOOKMARK_VIEW}.bookmark_service.list_bookmarked",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.get("/api/v1/chats/999/messages/bookmarked/")
    assert response.status_code == 404


def test_list_bookmarked_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/chats/1/messages/bookmarked/")
    assert response.status_code == 401
