import uuid

import pytest

from apps.chat.exceptions import (
    ChatAccessDeniedException,
    ChatNotFoundException,
    ShareLinkExpiredOrInactiveException,
    ShareLinkNotFoundException,
)
from core.exceptions.base import InsufficientPermissionsException
from test.conftest import make_message, make_share_link

SHARE_VIEW = "apps.chat.views.share_link_view"
PUBLIC_VIEW = "apps.chat.views.public_share_view"


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/chats/{chat_id}/share-links/
# ══════════════════════════════════════════════════════════════════════════════

def test_list_links_returns_200_paginated(api_client, mocker):
    link = make_share_link(link_id=1, chat_id=5)
    mocker.patch(f"{SHARE_VIEW}.share_link_service.list_links", return_value=[link])
    response = api_client.get("/api/v1/chats/5/share-links/")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["id"] == 1


def test_list_links_empty_returns_200(api_client, mocker):
    mocker.patch(f"{SHARE_VIEW}.share_link_service.list_links", return_value=[])
    response = api_client.get("/api/v1/chats/5/share-links/")
    assert response.status_code == 200
    assert response.data["results"] == []


def test_list_links_default_active_only_true(api_client, mocker):
    """Without ?active param, service is called with active_only=True."""
    svc = mocker.patch(f"{SHARE_VIEW}.share_link_service.list_links", return_value=[])
    api_client.get("/api/v1/chats/5/share-links/")
    _, kwargs = svc.call_args
    assert kwargs["active_only"] is True


def test_list_links_active_false_passes_to_service(api_client, mocker):
    svc = mocker.patch(f"{SHARE_VIEW}.share_link_service.list_links", return_value=[])
    api_client.get("/api/v1/chats/5/share-links/?active=false")
    _, kwargs = svc.call_args
    assert kwargs["active_only"] is False


def test_list_links_active_true_explicit(api_client, mocker):
    svc = mocker.patch(f"{SHARE_VIEW}.share_link_service.list_links", return_value=[])
    api_client.get("/api/v1/chats/5/share-links/?active=true")
    _, kwargs = svc.call_args
    assert kwargs["active_only"] is True


def test_list_links_active_uppercase_false_is_case_insensitive(api_client, mocker):
    """The `active` flag is normalized with .lower(), so FALSE also disables the filter."""
    svc = mocker.patch(f"{SHARE_VIEW}.share_link_service.list_links", return_value=[])
    api_client.get("/api/v1/chats/5/share-links/?active=FALSE")
    _, kwargs = svc.call_args
    assert kwargs["active_only"] is False


def test_list_links_response_includes_token_and_is_active(api_client, mocker):
    link = make_share_link(link_id=1, chat_id=5, is_active=True)
    mocker.patch(f"{SHARE_VIEW}.share_link_service.list_links", return_value=[link])
    response = api_client.get("/api/v1/chats/5/share-links/")
    result = response.data["results"][0]
    for field in ("id", "chat_id", "token", "created_by", "created_at", "expires_at", "is_active"):
        assert field in result, f"Missing field: {field}"
    assert result["is_active"] is True


def test_list_links_non_creator_returns_403(api_client, mocker):
    mocker.patch(
        f"{SHARE_VIEW}.share_link_service.list_links",
        side_effect=ChatAccessDeniedException(),
    )
    response = api_client.get("/api/v1/chats/5/share-links/")
    assert response.status_code == 403
    assert response.data["error"] == "chat_access_denied"


def test_list_links_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{SHARE_VIEW}.share_link_service.list_links",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.get("/api/v1/chats/999/share-links/")
    assert response.status_code == 404
    assert response.data["error"] == "chat_not_found"


def test_list_links_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{SHARE_VIEW}.share_link_service.list_links",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/chats/5/share-links/")
    assert response.status_code == 403


def test_list_links_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/chats/5/share-links/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/chats/{chat_id}/share-links/
# ══════════════════════════════════════════════════════════════════════════════

def test_create_link_returns_201_with_link_data(api_client, mocker):
    link = make_share_link(link_id=1, chat_id=5)
    mocker.patch(f"{SHARE_VIEW}.share_link_service.create_link", return_value=link)
    response = api_client.post("/api/v1/chats/5/share-links/", {}, format="json")
    assert response.status_code == 201
    assert response.data["id"] == 1
    assert "token" in response.data


def test_create_link_without_body_returns_201(api_client, mocker):
    """expires_at is optional — empty body is valid."""
    mocker.patch(f"{SHARE_VIEW}.share_link_service.create_link", return_value=make_share_link())
    response = api_client.post("/api/v1/chats/5/share-links/", {}, format="json")
    assert response.status_code == 201


def test_create_link_with_future_expires_at_returns_201(api_client, mocker):
    svc = mocker.patch(f"{SHARE_VIEW}.share_link_service.create_link", return_value=make_share_link())
    api_client.post(
        "/api/v1/chats/5/share-links/",
        {"expires_at": "2099-12-31T23:59:59Z"},
        format="json",
    )
    _, kwargs = svc.call_args
    assert kwargs["expires_at"] is not None


def test_create_link_explicit_null_expires_at_returns_201(api_client, mocker):
    """expires_at is allow_null — an explicit null is accepted and forwarded as None."""
    svc = mocker.patch(f"{SHARE_VIEW}.share_link_service.create_link", return_value=make_share_link())
    response = api_client.post(
        "/api/v1/chats/5/share-links/", {"expires_at": None}, format="json"
    )
    assert response.status_code == 201
    _, kwargs = svc.call_args
    assert kwargs["expires_at"] is None


def test_create_link_past_expires_at_returns_400(api_client, mocker):
    """expires_at in the past is rejected by the serializer validator."""
    mocker.patch(f"{SHARE_VIEW}.share_link_service.create_link")
    response = api_client.post(
        "/api/v1/chats/5/share-links/",
        {"expires_at": "2000-01-01T00:00:00Z"},
        format="json",
    )
    assert response.status_code == 400


def test_create_link_non_creator_returns_403(api_client, mocker):
    mocker.patch(
        f"{SHARE_VIEW}.share_link_service.create_link",
        side_effect=ChatAccessDeniedException(),
    )
    response = api_client.post("/api/v1/chats/5/share-links/", {}, format="json")
    assert response.status_code == 403
    assert response.data["error"] == "chat_access_denied"


def test_create_link_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{SHARE_VIEW}.share_link_service.create_link",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.post("/api/v1/chats/999/share-links/", {}, format="json")
    assert response.status_code == 404
    assert response.data["error"] == "chat_not_found"


def test_create_link_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{SHARE_VIEW}.share_link_service.create_link",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.post("/api/v1/chats/5/share-links/", {}, format="json")
    assert response.status_code == 403


def test_create_link_unauthenticated_returns_401(anon_client):
    response = anon_client.post("/api/v1/chats/5/share-links/", {}, format="json")
    assert response.status_code == 401


def test_create_link_passes_chat_id_and_expires_at_to_service(api_client, mocker):
    svc = mocker.patch(f"{SHARE_VIEW}.share_link_service.create_link", return_value=make_share_link())
    api_client.post(
        "/api/v1/chats/7/share-links/",
        {"expires_at": "2099-06-01T00:00:00Z"},
        format="json",
    )
    _, kwargs = svc.call_args
    assert kwargs["chat_id"] == 7
    assert kwargs["expires_at"] is not None


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /api/v1/chats/{chat_id}/share-links/{link_id}/
# ══════════════════════════════════════════════════════════════════════════════

def test_revoke_link_returns_204(api_client, mocker):
    mocker.patch(f"{SHARE_VIEW}.share_link_service.revoke_link")
    response = api_client.delete("/api/v1/chats/5/share-links/1/")
    assert response.status_code == 204
    assert not response.content


def test_revoke_link_passes_correct_ids_to_service(api_client, mocker):
    svc = mocker.patch(f"{SHARE_VIEW}.share_link_service.revoke_link")
    api_client.delete("/api/v1/chats/9/share-links/42/")
    _, kwargs = svc.call_args
    assert kwargs["chat_id"] == 9
    assert kwargs["link_id"] == 42


def test_revoke_link_non_creator_returns_403(api_client, mocker):
    mocker.patch(
        f"{SHARE_VIEW}.share_link_service.revoke_link",
        side_effect=ChatAccessDeniedException(),
    )
    response = api_client.delete("/api/v1/chats/5/share-links/1/")
    assert response.status_code == 403
    assert response.data["error"] == "chat_access_denied"


def test_revoke_link_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{SHARE_VIEW}.share_link_service.revoke_link",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.delete("/api/v1/chats/999/share-links/1/")
    assert response.status_code == 404
    assert response.data["error"] == "chat_not_found"


def test_revoke_link_link_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{SHARE_VIEW}.share_link_service.revoke_link",
        side_effect=ShareLinkNotFoundException(),
    )
    response = api_client.delete("/api/v1/chats/5/share-links/999/")
    assert response.status_code == 404
    assert response.data["error"] == "share_link_not_found"


def test_revoke_link_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{SHARE_VIEW}.share_link_service.revoke_link",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.delete("/api/v1/chats/5/share-links/1/")
    assert response.status_code == 403


def test_revoke_link_unauthenticated_returns_401(anon_client):
    response = anon_client.delete("/api/v1/chats/5/share-links/1/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/share/{token}/messages/  — public, no auth required
# ══════════════════════════════════════════════════════════════════════════════

def _token_url(token=None):
    t = token or uuid.uuid4()
    return f"/api/v1/share/{t}/messages/"


def test_public_messages_returns_200_paginated(anon_client, mocker):
    msgs = [make_message(msg_id=1), make_message(msg_id=2)]
    mocker.patch(f"{PUBLIC_VIEW}.share_link_service.get_public_messages", return_value=msgs)
    response = anon_client.get(_token_url())
    assert response.status_code == 200
    assert "results" in response.data


def test_public_messages_empty_chat_returns_200(anon_client, mocker):
    mocker.patch(f"{PUBLIC_VIEW}.share_link_service.get_public_messages", return_value=[])
    response = anon_client.get(_token_url())
    assert response.status_code == 200
    assert response.data["results"] == []


def test_public_messages_no_bearer_token_required(anon_client, mocker):
    """Public endpoint must work without Authorization header."""
    mocker.patch(f"{PUBLIC_VIEW}.share_link_service.get_public_messages", return_value=[])
    response = anon_client.get(_token_url())
    assert response.status_code == 200


def test_public_messages_authenticated_user_also_works(api_client, mocker):
    """Even authenticated users can access public share links."""
    mocker.patch(f"{PUBLIC_VIEW}.share_link_service.get_public_messages", return_value=[])
    response = api_client.get(_token_url())
    assert response.status_code == 200


def test_public_messages_passes_uuid_token_to_service(anon_client, mocker):
    token = uuid.uuid4()
    svc = mocker.patch(
        f"{PUBLIC_VIEW}.share_link_service.get_public_messages", return_value=[]
    )
    anon_client.get(f"/api/v1/share/{token}/messages/")
    args, _ = svc.call_args
    assert str(args[0]) == str(token)


def test_public_messages_token_not_found_returns_404(anon_client, mocker):
    mocker.patch(
        f"{PUBLIC_VIEW}.share_link_service.get_public_messages",
        side_effect=ShareLinkNotFoundException(),
    )
    response = anon_client.get(_token_url())
    assert response.status_code == 404
    assert response.data["error"] == "share_link_not_found"


def test_public_messages_inactive_link_returns_400(anon_client, mocker):
    mocker.patch(
        f"{PUBLIC_VIEW}.share_link_service.get_public_messages",
        side_effect=ShareLinkExpiredOrInactiveException(),
    )
    response = anon_client.get(_token_url())
    assert response.status_code == 400
    assert response.data["error"] == "share_link_expired_or_inactive"


def test_public_messages_expired_link_returns_400(anon_client, mocker):
    mocker.patch(
        f"{PUBLIC_VIEW}.share_link_service.get_public_messages",
        side_effect=ShareLinkExpiredOrInactiveException(),
    )
    response = anon_client.get(_token_url())
    assert response.status_code == 400


def test_public_messages_invalid_uuid_returns_404(anon_client):
    """A path that doesn't match <uuid:token> yields 404 from the URL router."""
    response = anon_client.get("/api/v1/share/not-a-uuid/messages/")
    assert response.status_code == 404


def test_public_messages_result_count_matches_mock(anon_client, mocker):
    msgs = [make_message(msg_id=i) for i in range(3)]
    mocker.patch(f"{PUBLIC_VIEW}.share_link_service.get_public_messages", return_value=msgs)
    response = anon_client.get(_token_url())
    assert response.data["count"] == 3
    assert len(response.data["results"]) == 3
