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


def test_submit_feedback_thumbs_down_forwards_reason_and_comment(api_client, mocker):
    set_feedback = mocker.patch(
        f"{FEEDBACK_VIEW}.feedback_service.set_feedback",
        return_value=make_feedback(value=-1, reason="incomplete", comment="Faltó detalle"),
    )
    response = api_client.post(
        "/api/v1/chats/1/messages/1/feedback/",
        {"value": -1, "reason": "incomplete", "comment": "Faltó detalle"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["reason"] == "incomplete"
    assert response.data["comment"] == "Faltó detalle"
    _, kwargs = set_feedback.call_args
    assert kwargs["reason"] == "incomplete"
    assert kwargs["comment"] == "Faltó detalle"


def test_submit_feedback_thumbs_up_drops_reason_and_comment(api_client, mocker):
    set_feedback = mocker.patch(
        f"{FEEDBACK_VIEW}.feedback_service.set_feedback",
        return_value=make_feedback(value=1),
    )
    response = api_client.post(
        "/api/v1/chats/1/messages/1/feedback/",
        {"value": 1, "reason": "incomplete", "comment": "ignored"},
        format="json",
    )
    assert response.status_code == 200
    _, kwargs = set_feedback.call_args
    assert kwargs["reason"] is None
    assert kwargs["comment"] is None


def test_submit_feedback_invalid_reason_returns_400(api_client, mocker):
    mocker.patch(f"{FEEDBACK_VIEW}.feedback_service.set_feedback")
    response = api_client.post(
        "/api/v1/chats/1/messages/1/feedback/",
        {"value": -1, "reason": "not_a_reason"},
        format="json",
    )
    assert response.status_code == 400


def test_submit_feedback_comment_too_long_returns_400(api_client, mocker):
    mocker.patch(f"{FEEDBACK_VIEW}.feedback_service.set_feedback")
    response = api_client.post(
        "/api/v1/chats/1/messages/1/feedback/",
        {"value": -1, "comment": "x" * 501},
        format="json",
    )
    assert response.status_code == 400


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
