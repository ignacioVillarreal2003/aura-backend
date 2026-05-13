from apps.message.exceptions import (
    MessageAccessDeniedException,
    MessageNotFoundException,
    NotAIMessageException,
)
from test.conftest import make_feedback


FEEDBACK_VIEW = "apps.message.views.feedback_view"


# ---------------------------------------------------------------------------
# Submit feedback  POST /api/v1/chats/{chat_id}/messages/{message_id}/feedback/
# ---------------------------------------------------------------------------

def test_submit_feedback_thumbs_up_returns_200(api_client, mocker):
    mocker.patch(
        f"{FEEDBACK_VIEW}.feedback_service.set_feedback",
        return_value=make_feedback(value=1),
    )
    response = api_client.post(
        "/api/v1/chats/1/messages/1/feedback/",
        {"value": 1},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["value"] == 1


def test_submit_feedback_thumbs_down_returns_200(api_client, mocker):
    mocker.patch(
        f"{FEEDBACK_VIEW}.feedback_service.set_feedback",
        return_value=make_feedback(value=-1),
    )
    response = api_client.post(
        "/api/v1/chats/1/messages/1/feedback/",
        {"value": -1},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["value"] == -1


def test_submit_feedback_invalid_value_returns_400(api_client, mocker):
    mocker.patch(f"{FEEDBACK_VIEW}.feedback_service.set_feedback")
    response = api_client.post(
        "/api/v1/chats/1/messages/1/feedback/",
        {"value": 0},
        format="json",
    )
    assert response.status_code == 400


def test_submit_feedback_missing_value_returns_400(api_client, mocker):
    mocker.patch(f"{FEEDBACK_VIEW}.feedback_service.set_feedback")
    response = api_client.post(
        "/api/v1/chats/1/messages/1/feedback/",
        {},
        format="json",
    )
    assert response.status_code == 400


def test_submit_feedback_not_ai_message_returns_400(api_client, mocker):
    mocker.patch(
        f"{FEEDBACK_VIEW}.feedback_service.set_feedback",
        side_effect=NotAIMessageException(),
    )
    response = api_client.post(
        "/api/v1/chats/1/messages/1/feedback/",
        {"value": 1},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["error"] == "not_ai_message"


def test_submit_feedback_message_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{FEEDBACK_VIEW}.feedback_service.set_feedback",
        side_effect=MessageNotFoundException(),
    )
    response = api_client.post(
        "/api/v1/chats/1/messages/999/feedback/",
        {"value": 1},
        format="json",
    )
    assert response.status_code == 404
    assert response.data["error"] == "message_not_found"


def test_submit_feedback_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{FEEDBACK_VIEW}.feedback_service.set_feedback",
        side_effect=MessageAccessDeniedException(),
    )
    response = api_client.post(
        "/api/v1/chats/1/messages/1/feedback/",
        {"value": 1},
        format="json",
    )
    assert response.status_code == 403


def test_submit_feedback_unauthenticated(anon_client):
    response = anon_client.post(
        "/api/v1/chats/1/messages/1/feedback/",
        {"value": 1},
        format="json",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Delete feedback  DELETE /api/v1/chats/{chat_id}/messages/{message_id}/feedback/
# ---------------------------------------------------------------------------

def test_delete_feedback_returns_204(api_client, mocker):
    mocker.patch(f"{FEEDBACK_VIEW}.feedback_service.delete_feedback")
    response = api_client.delete("/api/v1/chats/1/messages/1/feedback/")
    assert response.status_code == 204


def test_delete_feedback_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{FEEDBACK_VIEW}.feedback_service.delete_feedback",
        side_effect=MessageNotFoundException(),
    )
    response = api_client.delete("/api/v1/chats/1/messages/999/feedback/")
    assert response.status_code == 404


def test_delete_feedback_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{FEEDBACK_VIEW}.feedback_service.delete_feedback",
        side_effect=MessageAccessDeniedException(),
    )
    response = api_client.delete("/api/v1/chats/1/messages/1/feedback/")
    assert response.status_code == 403


def test_delete_feedback_unauthenticated(anon_client):
    response = anon_client.delete("/api/v1/chats/1/messages/1/feedback/")
    assert response.status_code == 401
