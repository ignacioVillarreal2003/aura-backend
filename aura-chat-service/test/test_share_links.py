import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.chat.exceptions import (
    ChatAccessDeniedException,
    ChatNotFoundException,
    ShareLinkExpiredOrInactiveException,
    ShareLinkNotFoundException,
)
from test.conftest import make_message, make_share_link


# ---------------------------------------------------------------------------
# List share links  GET /api/v1/chats/{chat_id}/share-links/
# ---------------------------------------------------------------------------

def test_list_share_links_returns_200(api_client, mocker):
    link = make_share_link()
    mocker.patch(
        "apps.chat.views.share_link_view.share_link_service.list_links",
        return_value=[link],
    )
    response = api_client.get("/api/v1/chats/1/share-links/")
    assert response.status_code == 200
    assert len(response.data["results"]) == 1


def test_list_share_links_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        "apps.chat.views.share_link_view.share_link_service.list_links",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.get("/api/v1/chats/999/share-links/")
    assert response.status_code == 404


def test_list_share_links_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        "apps.chat.views.share_link_view.share_link_service.list_links",
        side_effect=ChatAccessDeniedException(),
    )
    response = api_client.get("/api/v1/chats/1/share-links/")
    assert response.status_code == 403


def test_list_share_links_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/chats/1/share-links/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Create share link  POST /api/v1/chats/{chat_id}/share-links/
# ---------------------------------------------------------------------------

def test_create_share_link_returns_201(api_client, mocker):
    link = make_share_link()
    mocker.patch(
        "apps.chat.views.share_link_view.share_link_service.create_link",
        return_value=link,
    )
    response = api_client.post("/api/v1/chats/1/share-links/", {}, format="json")
    assert response.status_code == 201
    assert "token" in response.data


def test_create_share_link_with_future_expiry(api_client, mocker):
    svc = mocker.patch(
        "apps.chat.views.share_link_view.share_link_service.create_link",
        return_value=make_share_link(),
    )
    future = (timezone.now() + timedelta(days=7)).isoformat()
    api_client.post(
        "/api/v1/chats/1/share-links/",
        {"expires_at": future},
        format="json",
    )
    _, kwargs = svc.call_args
    assert kwargs["expires_at"] is not None


def test_create_share_link_past_expiry_returns_400(api_client, mocker):
    mocker.patch("apps.chat.views.share_link_view.share_link_service.create_link")
    past = (timezone.now() - timedelta(hours=1)).isoformat()
    response = api_client.post(
        "/api/v1/chats/1/share-links/",
        {"expires_at": past},
        format="json",
    )
    assert response.status_code == 400


def test_create_share_link_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        "apps.chat.views.share_link_view.share_link_service.create_link",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.post("/api/v1/chats/999/share-links/", {}, format="json")
    assert response.status_code == 404


def test_create_share_link_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        "apps.chat.views.share_link_view.share_link_service.create_link",
        side_effect=ChatAccessDeniedException(),
    )
    response = api_client.post("/api/v1/chats/1/share-links/", {}, format="json")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Revoke share link  DELETE /api/v1/chats/{chat_id}/share-links/{link_id}/
# ---------------------------------------------------------------------------

def test_revoke_share_link_returns_204(api_client, mocker):
    mocker.patch("apps.chat.views.share_link_view.share_link_service.revoke_link")
    response = api_client.delete("/api/v1/chats/1/share-links/1/")
    assert response.status_code == 204


def test_revoke_share_link_not_found_returns_404(api_client, mocker):
    mocker.patch(
        "apps.chat.views.share_link_view.share_link_service.revoke_link",
        side_effect=ShareLinkNotFoundException(),
    )
    response = api_client.delete("/api/v1/chats/1/share-links/999/")
    assert response.status_code == 404
    assert response.data["error"] == "share_link_not_found"


def test_revoke_share_link_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        "apps.chat.views.share_link_view.share_link_service.revoke_link",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.delete("/api/v1/chats/999/share-links/1/")
    assert response.status_code == 404


def test_revoke_share_link_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        "apps.chat.views.share_link_view.share_link_service.revoke_link",
        side_effect=ChatAccessDeniedException(),
    )
    response = api_client.delete("/api/v1/chats/1/share-links/1/")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Public share messages  GET /api/v1/share/{token}/messages/
# ---------------------------------------------------------------------------

def test_public_share_messages_returns_200(anon_client, mocker):
    mocker.patch(
        "apps.chat.views.public_share_view.share_link_service.get_public_messages",
        return_value=[make_message()],
    )
    token = uuid.uuid4()
    response = anon_client.get(f"/api/v1/share/{token}/messages/")
    assert response.status_code == 200
    assert len(response.data["results"]) == 1


def test_public_share_messages_no_auth_required(anon_client, mocker):
    mocker.patch(
        "apps.chat.views.public_share_view.share_link_service.get_public_messages",
        return_value=[],
    )
    token = uuid.uuid4()
    response = anon_client.get(f"/api/v1/share/{token}/messages/")
    assert response.status_code == 200


def test_public_share_messages_not_found_returns_404(anon_client, mocker):
    mocker.patch(
        "apps.chat.views.public_share_view.share_link_service.get_public_messages",
        side_effect=ShareLinkNotFoundException(),
    )
    token = uuid.uuid4()
    response = anon_client.get(f"/api/v1/share/{token}/messages/")
    assert response.status_code == 404


def test_public_share_messages_expired_returns_400(anon_client, mocker):
    mocker.patch(
        "apps.chat.views.public_share_view.share_link_service.get_public_messages",
        side_effect=ShareLinkExpiredOrInactiveException(),
    )
    token = uuid.uuid4()
    response = anon_client.get(f"/api/v1/share/{token}/messages/")
    assert response.status_code == 400
    assert response.data["error"] == "share_link_expired_or_inactive"
