"""
Chat views — HTTP layer tests

Endpoints covered:
    GET    /api/v1/chats/                     ChatViewSet.list
    POST   /api/v1/chats/                     ChatViewSet.create
    GET    /api/v1/chats/{chat_id}/           ChatViewSet.retrieve
    PATCH  /api/v1/chats/{chat_id}/           ChatViewSet.partial_update
    DELETE /api/v1/chats/{chat_id}/           ChatViewSet.destroy
    GET    /api/v1/chats/me/                  ChatViewSet.my_chats
    GET    /api/v1/chats/manage/              ChatViewSet.manage
    GET    /api/v1/chats/archived/            ChatViewSet.archived
    POST   /api/v1/chats/archive/            ChatViewSet.archive
    POST   /api/v1/chats/unarchive/          ChatViewSet.unarchive
    POST   /DELETE /api/v1/chats/{chat_id}/pin/    ChatViewSet.pin
    POST   /DELETE /api/v1/chats/{chat_id}/lock/   ChatViewSet.lock
"""
import pytest

from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from core.exceptions.base import InsufficientPermissionsException
from test.conftest import make_chat

VIEW = "apps.chat.views.chat_view"


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/chats/  (list)
# ══════════════════════════════════════════════════════════════════════════════

def test_list_returns_paginated_results(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.list_chats", return_value=[make_chat()])
    response = api_client.get("/api/v1/chats/")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1


def test_list_forwards_search_ordering_tags(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.chat_service.list_chats", return_value=[])
    api_client.get("/api/v1/chats/?search=hi&ordering=name&tags=a,b")
    _, kwargs = svc.call_args
    assert kwargs["search"] == "hi"
    assert kwargs["ordering"] == "name"
    assert kwargs["tags"] == ["a", "b"]


def test_list_invalid_ordering_falls_back_to_none(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.chat_service.list_chats", return_value=[])
    api_client.get("/api/v1/chats/?ordering=bogus")
    _, kwargs = svc.call_args
    assert kwargs["ordering"] is None


def test_list_blank_tags_become_none(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.chat_service.list_chats", return_value=[])
    api_client.get("/api/v1/chats/?tags=,, ,")
    _, kwargs = svc.call_args
    assert kwargs["tags"] is None


def test_list_unauthenticated_returns_401(anon_client):
    assert anon_client.get("/api/v1/chats/").status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/chats/  (create — permission only, no ownership)
# ══════════════════════════════════════════════════════════════════════════════

def test_create_returns_201(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.create_chat", return_value=make_chat())
    response = api_client.post("/api/v1/chats/", {"name": "My Chat"}, format="json")
    assert response.status_code == 201
    assert response.data["name"] == "Test Chat"


def test_create_forwards_validated_data(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.chat_service.create_chat", return_value=make_chat())
    api_client.post(
        "/api/v1/chats/",
        {"name": "X", "tags": ["a", " a ", "b"]},
        format="json",
    )
    _, kwargs = svc.call_args
    assert kwargs["name"] == "X"
    assert kwargs["tags"] == ["a", "b"]


def test_create_missing_name_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.create_chat")
    assert api_client.post("/api/v1/chats/", {}, format="json").status_code == 400


def test_create_too_many_tags_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.create_chat")
    tags = [f"tag{i}" for i in range(21)]
    response = api_client.post("/api/v1/chats/", {"name": "C", "tags": tags}, format="json")
    assert response.status_code == 400


def test_create_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.chat_service.create_chat",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.post("/api/v1/chats/", {"name": "C"}, format="json")
    assert response.status_code == 403


def test_create_unauthenticated_returns_401(anon_client):
    assert anon_client.post("/api/v1/chats/", {"name": "C"}, format="json").status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/chats/{chat_id}/  (retrieve)
# ══════════════════════════════════════════════════════════════════════════════

def test_retrieve_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.get_chat", return_value=make_chat())
    response = api_client.get("/api/v1/chats/1/")
    assert response.status_code == 200
    assert response.data["id"] == 1


def test_retrieve_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.get_chat", side_effect=ChatNotFoundException())
    response = api_client.get("/api/v1/chats/999/")
    assert response.status_code == 404
    assert response.data["error"] == "chat_not_found"


def test_retrieve_access_denied_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.get_chat", side_effect=ChatAccessDeniedException())
    response = api_client.get("/api/v1/chats/1/")
    assert response.status_code == 403
    assert response.data["error"] == "chat_access_denied"


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /api/v1/chats/{chat_id}/  (update — global / owner-or-creator)
# ══════════════════════════════════════════════════════════════════════════════

def test_update_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.update_chat", return_value=make_chat(name="Updated"))
    response = api_client.patch("/api/v1/chats/1/", {"name": "Updated"}, format="json")
    assert response.status_code == 200
    assert response.data["name"] == "Updated"


def test_update_normalizes_tags(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.chat_service.update_chat", return_value=make_chat())
    api_client.patch("/api/v1/chats/1/", {"tags": ["a", " a ", "b"]}, format="json")
    _, kwargs = svc.call_args
    assert kwargs["tags"] == ["a", "b"]


def test_update_empty_body_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.update_chat")
    assert api_client.patch("/api/v1/chats/1/", {}, format="json").status_code == 400


def test_update_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.update_chat", side_effect=ChatNotFoundException())
    response = api_client.patch("/api/v1/chats/999/", {"name": "X"}, format="json")
    assert response.status_code == 404


def test_update_access_denied_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.update_chat", side_effect=ChatAccessDeniedException())
    response = api_client.patch("/api/v1/chats/1/", {"name": "X"}, format="json")
    assert response.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /api/v1/chats/{chat_id}/  (delete — global / owner-or-creator)
# ══════════════════════════════════════════════════════════════════════════════

def test_delete_returns_204(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.delete_chat")
    assert api_client.delete("/api/v1/chats/1/").status_code == 204


def test_delete_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.delete_chat", side_effect=ChatNotFoundException())
    assert api_client.delete("/api/v1/chats/999/").status_code == 404


def test_delete_access_denied_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.delete_chat", side_effect=ChatAccessDeniedException())
    assert api_client.delete("/api/v1/chats/1/").status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/chats/me/  (my_chats)
# ══════════════════════════════════════════════════════════════════════════════

def test_my_chats_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.list_own_chats", return_value=[make_chat()])
    response = api_client.get("/api/v1/chats/me/")
    assert response.status_code == 200
    assert len(response.data["results"]) == 1


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/chats/manage/  (admin)
# ══════════════════════════════════════════════════════════════════════════════

def test_manage_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.list_all_chats", return_value=[make_chat()])
    response = api_client.get("/api/v1/chats/manage/")
    assert response.status_code == 200
    assert len(response.data["results"]) == 1


def test_manage_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.chat_service.list_all_chats",
        side_effect=InsufficientPermissionsException(),
    )
    assert api_client.get("/api/v1/chats/manage/").status_code == 403


def test_manage_forwards_filters(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.chat_service.list_all_chats", return_value=[])
    api_client.get("/api/v1/chats/manage/?search=q&ordering=-name")
    _, kwargs = svc.call_args
    assert kwargs["search"] == "q"
    assert kwargs["ordering"] == "-name"


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/chats/archived/  +  POST archive / unarchive
# ══════════════════════════════════════════════════════════════════════════════

def test_archived_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.list_archived_chats", return_value=[])
    response = api_client.get("/api/v1/chats/archived/")
    assert response.status_code == 200
    assert response.data["results"] == []


def test_archive_returns_count(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.archive_chats", return_value=2)
    response = api_client.post("/api/v1/chats/archive/", {"ids": [1, 2]}, format="json")
    assert response.status_code == 200
    assert response.data["archived"] == 2


def test_archive_empty_ids_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.archive_chats")
    assert api_client.post("/api/v1/chats/archive/", {"ids": []}, format="json").status_code == 400


def test_archive_inaccessible_chat_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.archive_chats", side_effect=ChatNotFoundException())
    response = api_client.post("/api/v1/chats/archive/", {"ids": [1, 99]}, format="json")
    assert response.status_code == 404


def test_unarchive_returns_count(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.unarchive_chats", return_value=1)
    response = api_client.post("/api/v1/chats/unarchive/", {"ids": [1]}, format="json")
    assert response.status_code == 200
    assert response.data["unarchived"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# POST/DELETE /api/v1/chats/{chat_id}/pin/  (personal)
# ══════════════════════════════════════════════════════════════════════════════

def test_pin_returns_204(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.pin_chat")
    assert api_client.post("/api/v1/chats/1/pin/").status_code == 204


def test_unpin_returns_204(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.unpin_chat")
    assert api_client.delete("/api/v1/chats/1/pin/").status_code == 204


def test_pin_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.pin_chat", side_effect=ChatNotFoundException())
    assert api_client.post("/api/v1/chats/999/pin/").status_code == 404


def test_pin_non_member_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.pin_chat", side_effect=ChatAccessDeniedException())
    assert api_client.post("/api/v1/chats/1/pin/").status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# POST/DELETE /api/v1/chats/{chat_id}/lock/  (global / owner-or-creator)
# ══════════════════════════════════════════════════════════════════════════════

def test_lock_returns_204(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.lock_chat")
    assert api_client.post("/api/v1/chats/1/lock/").status_code == 204


def test_unlock_returns_204(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.unlock_chat")
    assert api_client.delete("/api/v1/chats/1/lock/").status_code == 204


def test_lock_access_denied_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.lock_chat", side_effect=ChatAccessDeniedException())
    assert api_client.post("/api/v1/chats/1/lock/").status_code == 403


def test_unlock_access_denied_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.unlock_chat", side_effect=ChatAccessDeniedException())
    assert api_client.delete("/api/v1/chats/1/lock/").status_code == 403


def test_lock_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.chat_service.lock_chat", side_effect=ChatNotFoundException())
    assert api_client.post("/api/v1/chats/999/lock/").status_code == 404
