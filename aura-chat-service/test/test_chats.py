from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from core.exceptions.base import InsufficientPermissionsException
from test.conftest import make_chat


# ---------------------------------------------------------------------------
# List chats  GET /api/v1/chats/
# ---------------------------------------------------------------------------

def test_list_chats_returns_paginated_results(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.list_chats",
        return_value=[make_chat()],
    )
    response = api_client.get("/api/v1/chats/")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1


def test_list_chats_with_search_filter(api_client, mocker):
    svc = mocker.patch(
        "apps.chat.views.chat_view.chat_service.list_chats",
        return_value=[],
    )
    api_client.get("/api/v1/chats/?search=hello")
    svc.assert_called_once()
    _, kwargs = svc.call_args
    assert kwargs["search"] == "hello"


def test_list_chats_with_tags_filter(api_client, mocker):
    svc = mocker.patch(
        "apps.chat.views.chat_view.chat_service.list_chats",
        return_value=[],
    )
    api_client.get("/api/v1/chats/?tags=work,urgent")
    _, kwargs = svc.call_args
    assert "work" in kwargs["tags"]
    assert "urgent" in kwargs["tags"]


def test_list_chats_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/chats/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Create chat  POST /api/v1/chats/
# ---------------------------------------------------------------------------

def test_create_chat_returns_201(api_client, mocker):
    chat = make_chat()
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.create_chat",
        return_value=chat,
    )
    response = api_client.post(
        "/api/v1/chats/",
        {"name": "My Chat", "tags": ["tag1"]},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["name"] == "Test Chat"


def test_create_chat_missing_name_returns_400(api_client, mocker):
    mocker.patch("apps.chat.views.chat_view.chat_service.create_chat")
    response = api_client.post("/api/v1/chats/", {}, format="json")
    assert response.status_code == 400


def test_create_chat_too_many_tags_returns_400(api_client, mocker):
    mocker.patch("apps.chat.views.chat_view.chat_service.create_chat")
    tags = [f"tag{i}" for i in range(21)]
    response = api_client.post(
        "/api/v1/chats/",
        {"name": "Chat", "tags": tags},
        format="json",
    )
    assert response.status_code == 400


def test_create_chat_unauthenticated(anon_client):
    response = anon_client.post("/api/v1/chats/", {"name": "Chat"}, format="json")
    assert response.status_code == 401


def test_create_chat_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.create_chat",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.post("/api/v1/chats/", {"name": "Chat"}, format="json")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Get chat  GET /api/v1/chats/{pk}/
# ---------------------------------------------------------------------------

def test_get_chat_returns_200(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.get_chat",
        return_value=make_chat(),
    )
    response = api_client.get("/api/v1/chats/1/")
    assert response.status_code == 200
    assert response.data["id"] == 1


def test_get_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.get_chat",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.get("/api/v1/chats/999/")
    assert response.status_code == 404
    assert response.data["error"] == "chat_not_found"


def test_get_chat_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.get_chat",
        side_effect=ChatAccessDeniedException(),
    )
    response = api_client.get("/api/v1/chats/1/")
    assert response.status_code == 403
    assert response.data["error"] == "chat_access_denied"


def test_get_chat_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/chats/1/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Update chat  PATCH /api/v1/chats/{pk}/
# ---------------------------------------------------------------------------

def test_update_chat_returns_200(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.update_chat",
        return_value=make_chat(name="Updated"),
    )
    response = api_client.patch(
        "/api/v1/chats/1/",
        {"name": "Updated"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["name"] == "Updated"


def test_update_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.update_chat",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.patch("/api/v1/chats/999/", {"name": "X"}, format="json")
    assert response.status_code == 404


def test_update_chat_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.update_chat",
        side_effect=ChatAccessDeniedException(),
    )
    response = api_client.patch("/api/v1/chats/1/", {"name": "X"}, format="json")
    assert response.status_code == 403


def test_update_chat_normalizes_tags(api_client, mocker):
    svc = mocker.patch(
        "apps.chat.views.chat_view.chat_service.update_chat",
        return_value=make_chat(),
    )
    api_client.patch("/api/v1/chats/1/", {"tags": ["a", " a ", "b"]}, format="json")
    _, kwargs = svc.call_args
    assert kwargs["tags"] == ["a", "b"]


# ---------------------------------------------------------------------------
# Delete chat  DELETE /api/v1/chats/{pk}/
# ---------------------------------------------------------------------------

def test_delete_chat_returns_204(api_client, mocker):
    mocker.patch("apps.chat.views.chat_view.chat_service.delete_chat")
    response = api_client.delete("/api/v1/chats/1/")
    assert response.status_code == 204


def test_delete_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.delete_chat",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.delete("/api/v1/chats/999/")
    assert response.status_code == 404


def test_delete_chat_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.delete_chat",
        side_effect=ChatAccessDeniedException(),
    )
    response = api_client.delete("/api/v1/chats/1/")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# My chats  GET /api/v1/chats/me/
# ---------------------------------------------------------------------------

def test_my_chats_returns_200(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.list_own_chats",
        return_value=[make_chat()],
    )
    response = api_client.get("/api/v1/chats/me/")
    assert response.status_code == 200
    assert len(response.data["results"]) == 1


# ---------------------------------------------------------------------------
# Archived chats  GET /api/v1/chats/archived/
# ---------------------------------------------------------------------------

def test_archived_chats_returns_200(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.list_archived_chats",
        return_value=[],
    )
    response = api_client.get("/api/v1/chats/archived/")
    assert response.status_code == 200
    assert response.data["results"] == []


# ---------------------------------------------------------------------------
# Archive/unarchive  POST /api/v1/chats/archive|unarchive/
# ---------------------------------------------------------------------------

def test_archive_chats_returns_count(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.archive_chats",
        return_value=2,
    )
    response = api_client.post(
        "/api/v1/chats/archive/",
        {"ids": [1, 2]},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["archived"] == 2


def test_archive_chats_empty_ids_returns_400(api_client, mocker):
    mocker.patch("apps.chat.views.chat_view.chat_service.archive_chats")
    response = api_client.post("/api/v1/chats/archive/", {"ids": []}, format="json")
    assert response.status_code == 400


def test_unarchive_chats_returns_count(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.unarchive_chats",
        return_value=1,
    )
    response = api_client.post(
        "/api/v1/chats/unarchive/",
        {"ids": [1]},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["unarchived"] == 1


# ---------------------------------------------------------------------------
# Pin/unpin  POST|DELETE /api/v1/chats/{pk}/pin/
# ---------------------------------------------------------------------------

def test_pin_chat_returns_204(api_client, mocker):
    mocker.patch("apps.chat.views.chat_view.chat_service.pin_chat")
    response = api_client.post("/api/v1/chats/1/pin/")
    assert response.status_code == 204


def test_unpin_chat_returns_204(api_client, mocker):
    mocker.patch("apps.chat.views.chat_view.chat_service.unpin_chat")
    response = api_client.delete("/api/v1/chats/1/pin/")
    assert response.status_code == 204


def test_pin_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.pin_chat",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.post("/api/v1/chats/999/pin/")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Lock/unlock  POST|DELETE /api/v1/chats/{pk}/lock/
# ---------------------------------------------------------------------------

def test_lock_chat_returns_204(api_client, mocker):
    mocker.patch("apps.chat.views.chat_view.chat_service.lock_chat")
    response = api_client.post("/api/v1/chats/1/lock/")
    assert response.status_code == 204


def test_unlock_chat_returns_204(api_client, mocker):
    mocker.patch("apps.chat.views.chat_view.chat_service.unlock_chat")
    response = api_client.delete("/api/v1/chats/1/lock/")
    assert response.status_code == 204


def test_lock_chat_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.lock_chat",
        side_effect=ChatAccessDeniedException(),
    )
    response = api_client.post("/api/v1/chats/1/lock/")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Mute/unmute  POST|DELETE /api/v1/chats/{pk}/mute/
# ---------------------------------------------------------------------------

def test_mute_chat_returns_204(api_client, mocker):
    mocker.patch("apps.chat.views.chat_view.chat_service.mute_chat")
    future = (timezone.now() + timedelta(hours=1)).isoformat()
    response = api_client.post(
        "/api/v1/chats/1/mute/",
        {"muted_until": future},
        format="json",
    )
    assert response.status_code == 204


def test_mute_chat_past_datetime_returns_400(api_client, mocker):
    mocker.patch("apps.chat.views.chat_view.chat_service.mute_chat")
    past = (timezone.now() - timedelta(hours=1)).isoformat()
    response = api_client.post(
        "/api/v1/chats/1/mute/",
        {"muted_until": past},
        format="json",
    )
    assert response.status_code == 400


def test_mute_chat_missing_field_returns_400(api_client, mocker):
    mocker.patch("apps.chat.views.chat_view.chat_service.mute_chat")
    response = api_client.post("/api/v1/chats/1/mute/", {}, format="json")
    assert response.status_code == 400


def test_unmute_chat_returns_204(api_client, mocker):
    mocker.patch("apps.chat.views.chat_view.chat_service.unmute_chat")
    response = api_client.delete("/api/v1/chats/1/mute/")
    assert response.status_code == 204


def test_unmute_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        "apps.chat.views.chat_view.chat_service.unmute_chat",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.delete("/api/v1/chats/999/mute/")
    assert response.status_code == 404
