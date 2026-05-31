import pytest

from apps.assistant.exceptions import (
    AssistantAlreadyExistsException,
    AssistantInactiveException,
    AssistantNotFoundException,
)
from core.exceptions.base import InsufficientPermissionsException
from test.conftest import make_assistant, make_chat

VIEW = "apps.assistant.views"


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/assistants/  — list active (user)
# ══════════════════════════════════════════════════════════════════════════════

def test_list_active_returns_200_paginated(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.list_active_assistants", return_value=[make_assistant()])
    response = api_client.get("/api/v1/assistants/")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["id"] == 1


def test_list_active_empty_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.list_active_assistants", return_value=[])
    response = api_client.get("/api/v1/assistants/")
    assert response.status_code == 200
    assert response.data["results"] == []


def test_list_active_passes_search_to_service(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.assistant_service.list_active_assistants", return_value=[])
    api_client.get("/api/v1/assistants/?search=alfa")
    _, kwargs = svc.call_args
    assert kwargs["search"] == "alfa"


def test_list_active_empty_search_passes_none(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.assistant_service.list_active_assistants", return_value=[])
    api_client.get("/api/v1/assistants/?search=")
    _, kwargs = svc.call_args
    assert kwargs["search"] is None


def test_list_active_does_not_expose_system_prompt(api_client, mocker):
    """User-facing list must NOT include system_prompt."""
    mocker.patch(f"{VIEW}.assistant_service.list_active_assistants", return_value=[make_assistant()])
    response = api_client.get("/api/v1/assistants/")
    result = response.data["results"][0]
    assert "system_prompt" not in result
    assert "response_style" not in result


def test_list_active_response_fields(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.list_active_assistants", return_value=[make_assistant()])
    response = api_client.get("/api/v1/assistants/")
    result = response.data["results"][0]
    for field in ("id", "name", "description", "avatar_emoji", "is_active", "created_at"):
        assert field in result, f"Missing field: {field}"


def test_list_active_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.list_active_assistants",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/assistants/")
    assert response.status_code == 403


def test_list_active_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/assistants/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/assistants/  — create (admin)
# ══════════════════════════════════════════════════════════════════════════════

_VALID_CREATE = {
    "name": "Asistente Nuevo",
    "system_prompt": "Sé útil y conciso.",
    "description": "Descripción del asistente.",
    "avatar_emoji": "🤖",
    "is_active": True,
}


def test_create_assistant_returns_201_with_admin_response(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.create_assistant", return_value=make_assistant())
    response = api_client.post("/api/v1/assistants/", _VALID_CREATE, format="json")
    assert response.status_code == 201
    data = response.data
    assert data["id"] == 1
    assert "system_prompt" in data


def test_create_assistant_forwards_fields_to_service(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.assistant_service.create_assistant", return_value=make_assistant())
    api_client.post("/api/v1/assistants/", _VALID_CREATE, format="json")
    _, kwargs = svc.call_args
    assert kwargs["name"] == "Asistente Nuevo"
    assert kwargs["system_prompt"] == "Sé útil y conciso."
    assert kwargs["is_active"] is True


def test_create_assistant_description_optional(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.create_assistant", return_value=make_assistant())
    payload = {"name": "X", "system_prompt": "Prompt"}
    response = api_client.post("/api/v1/assistants/", payload, format="json")
    assert response.status_code == 201


def test_create_assistant_missing_name_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.create_assistant")
    response = api_client.post(
        "/api/v1/assistants/", {"system_prompt": "Prompt"}, format="json"
    )
    assert response.status_code == 400


def test_create_assistant_blank_name_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.create_assistant")
    response = api_client.post(
        "/api/v1/assistants/", {"name": "  ", "system_prompt": "Prompt"}, format="json"
    )
    assert response.status_code == 400


def test_create_assistant_missing_system_prompt_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.create_assistant")
    response = api_client.post(
        "/api/v1/assistants/", {"name": "X"}, format="json"
    )
    assert response.status_code == 400


def test_create_assistant_blank_system_prompt_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.create_assistant")
    response = api_client.post(
        "/api/v1/assistants/", {"name": "X", "system_prompt": ""}, format="json"
    )
    assert response.status_code == 400


def test_create_assistant_name_over_256_chars_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.create_assistant")
    response = api_client.post(
        "/api/v1/assistants/",
        {"name": "A" * 257, "system_prompt": "Prompt"},
        format="json",
    )
    assert response.status_code == 400


def test_create_assistant_system_prompt_over_8000_chars_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.create_assistant")
    response = api_client.post(
        "/api/v1/assistants/",
        {"name": "X", "system_prompt": "x" * 8001},
        format="json",
    )
    assert response.status_code == 400


def test_create_assistant_system_prompt_exactly_8000_chars_is_valid(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.create_assistant", return_value=make_assistant())
    response = api_client.post(
        "/api/v1/assistants/",
        {"name": "X", "system_prompt": "x" * 8000},
        format="json",
    )
    assert response.status_code == 201


def test_create_assistant_response_style_over_2000_chars_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.create_assistant")
    response = api_client.post(
        "/api/v1/assistants/",
        {"name": "X", "system_prompt": "P", "response_style": "x" * 2001},
        format="json",
    )
    assert response.status_code == 400


def test_create_assistant_avatar_emoji_over_16_chars_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.create_assistant")
    response = api_client.post(
        "/api/v1/assistants/",
        {"name": "X", "system_prompt": "P", "avatar_emoji": "x" * 17},
        format="json",
    )
    assert response.status_code == 400


def test_create_assistant_is_active_defaults_true(api_client, mocker):
    """When is_active is omitted, the serializer default (True) reaches the service."""
    svc = mocker.patch(f"{VIEW}.assistant_service.create_assistant", return_value=make_assistant())
    api_client.post("/api/v1/assistants/", {"name": "X", "system_prompt": "P"}, format="json")
    _, kwargs = svc.call_args
    assert kwargs["is_active"] is True


def test_create_assistant_name_conflict_returns_409(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.create_assistant",
        side_effect=AssistantAlreadyExistsException(),
    )
    response = api_client.post("/api/v1/assistants/", _VALID_CREATE, format="json")
    assert response.status_code == 409
    assert response.data["error"] == "assistant_already_exists"


def test_create_assistant_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.create_assistant",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.post("/api/v1/assistants/", _VALID_CREATE, format="json")
    assert response.status_code == 403


def test_create_assistant_unauthenticated_returns_401(anon_client):
    response = anon_client.post("/api/v1/assistants/", _VALID_CREATE, format="json")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/assistants/manage/  — list all (admin)
# ══════════════════════════════════════════════════════════════════════════════

def test_manage_list_returns_200_with_all_assistants(api_client, mocker):
    active = make_assistant(assistant_id=1, is_active=True)
    inactive = make_assistant(assistant_id=2, is_active=False, name="Inactivo")
    mocker.patch(f"{VIEW}.assistant_service.list_all_assistants", return_value=[active, inactive])
    response = api_client.get("/api/v1/assistants/manage/")
    assert response.status_code == 200
    assert len(response.data["results"]) == 2


def test_manage_list_response_includes_system_prompt(api_client, mocker):
    """Admin list must include system_prompt."""
    mocker.patch(
        f"{VIEW}.assistant_service.list_all_assistants",
        return_value=[make_assistant(system_prompt="Secreto")],
    )
    response = api_client.get("/api/v1/assistants/manage/")
    result = response.data["results"][0]
    assert "system_prompt" in result
    assert result["system_prompt"] == "Secreto"


def test_manage_list_passes_search_to_service(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.assistant_service.list_all_assistants", return_value=[])
    api_client.get("/api/v1/assistants/manage/?search=beta")
    _, kwargs = svc.call_args
    assert kwargs["search"] == "beta"


def test_manage_list_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.list_all_assistants",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/assistants/manage/")
    assert response.status_code == 403


def test_manage_list_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/assistants/manage/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/assistants/{id}/  — get detail (user)
# ══════════════════════════════════════════════════════════════════════════════

def test_get_assistant_returns_200(api_client, mocker):
    assistant = make_assistant(assistant_id=3, name="Táctico")
    mocker.patch(f"{VIEW}.assistant_service.get_assistant", return_value=assistant)
    response = api_client.get("/api/v1/assistants/3/")
    assert response.status_code == 200
    assert response.data["id"] == 3
    assert response.data["name"] == "Táctico"


def test_get_assistant_does_not_expose_system_prompt(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.get_assistant", return_value=make_assistant())
    response = api_client.get("/api/v1/assistants/1/")
    assert "system_prompt" not in response.data
    assert "response_style" not in response.data


def test_get_assistant_response_fields(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.get_assistant", return_value=make_assistant())
    response = api_client.get("/api/v1/assistants/1/")
    for field in ("id", "name", "description", "avatar_emoji", "is_active", "created_at"):
        assert field in response.data, f"Missing field: {field}"


def test_get_assistant_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.get_assistant",
        side_effect=AssistantNotFoundException(),
    )
    response = api_client.get("/api/v1/assistants/999/")
    assert response.status_code == 404
    assert response.data["error"] == "assistant_not_found"


def test_get_assistant_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.get_assistant",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/assistants/1/")
    assert response.status_code == 403


def test_get_assistant_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/assistants/1/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /api/v1/assistants/{id}/  — update (admin)
# ══════════════════════════════════════════════════════════════════════════════

def test_patch_name_returns_200_with_admin_response(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.update_assistant",
        return_value=make_assistant(name="Actualizado"),
    )
    response = api_client.patch("/api/v1/assistants/1/", {"name": "Actualizado"}, format="json")
    assert response.status_code == 200
    assert response.data["name"] == "Actualizado"
    assert "system_prompt" in response.data


def test_patch_is_active_false_deactivates(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.update_assistant",
        return_value=make_assistant(is_active=False),
    )
    response = api_client.patch("/api/v1/assistants/1/", {"is_active": False}, format="json")
    assert response.status_code == 200
    assert response.data["is_active"] is False


def test_patch_forwards_all_fields_to_service(api_client, mocker):
    svc = mocker.patch(
        f"{VIEW}.assistant_service.update_assistant",
        return_value=make_assistant(),
    )
    api_client.patch(
        "/api/v1/assistants/5/",
        {
            "name": "Nuevo",
            "description": "Desc",
            "system_prompt": "Prompt",
            "response_style": "breve",
            "avatar_emoji": "⚡",
            "is_active": True,
        },
        format="json",
    )
    _, kwargs = svc.call_args
    assert kwargs["assistant_id"] == 5
    assert kwargs["name"] == "Nuevo"
    assert kwargs["system_prompt"] == "Prompt"
    assert kwargs["is_active"] is True

def test_patch_blank_name_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.update_assistant")
    response = api_client.patch("/api/v1/assistants/1/", {"name": "  "}, format="json")
    assert response.status_code == 400


def test_patch_blank_system_prompt_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.update_assistant")
    response = api_client.patch("/api/v1/assistants/1/", {"system_prompt": ""}, format="json")
    assert response.status_code == 400


def test_patch_name_over_256_chars_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.update_assistant")
    response = api_client.patch(
        "/api/v1/assistants/1/", {"name": "A" * 257}, format="json"
    )
    assert response.status_code == 400


def test_patch_system_prompt_over_8000_chars_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.update_assistant")
    response = api_client.patch(
        "/api/v1/assistants/1/", {"system_prompt": "x" * 8001}, format="json"
    )
    assert response.status_code == 400


def test_patch_response_style_over_2000_chars_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.update_assistant")
    response = api_client.patch(
        "/api/v1/assistants/1/", {"response_style": "x" * 2001}, format="json"
    )
    assert response.status_code == 400


def test_patch_avatar_emoji_over_16_chars_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.update_assistant")
    response = api_client.patch(
        "/api/v1/assistants/1/", {"avatar_emoji": "x" * 17}, format="json"
    )
    assert response.status_code == 400


def test_patch_name_conflict_returns_409(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.update_assistant",
        side_effect=AssistantAlreadyExistsException(),
    )
    response = api_client.patch("/api/v1/assistants/1/", {"name": "Duplicado"}, format="json")
    assert response.status_code == 409
    assert response.data["error"] == "assistant_already_exists"


def test_patch_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.update_assistant",
        side_effect=AssistantNotFoundException(),
    )
    response = api_client.patch("/api/v1/assistants/999/", {"name": "X"}, format="json")
    assert response.status_code == 404
    assert response.data["error"] == "assistant_not_found"


def test_patch_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.update_assistant",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.patch("/api/v1/assistants/1/", {"name": "X"}, format="json")
    assert response.status_code == 403


def test_patch_unauthenticated_returns_401(anon_client):
    response = anon_client.patch("/api/v1/assistants/1/", {"name": "X"}, format="json")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /api/v1/assistants/{id}/  — delete (admin)
# ══════════════════════════════════════════════════════════════════════════════

def test_delete_assistant_returns_204(api_client, mocker):
    mocker.patch(f"{VIEW}.assistant_service.delete_assistant")
    response = api_client.delete("/api/v1/assistants/1/")
    assert response.status_code == 204
    assert not response.content


def test_delete_assistant_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.delete_assistant",
        side_effect=AssistantNotFoundException(),
    )
    response = api_client.delete("/api/v1/assistants/999/")
    assert response.status_code == 404
    assert response.data["error"] == "assistant_not_found"


def test_delete_assistant_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.delete_assistant",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.delete("/api/v1/assistants/1/")
    assert response.status_code == 403


def test_delete_assistant_unauthenticated_returns_401(anon_client):
    response = anon_client.delete("/api/v1/assistants/1/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/assistants/{id}/start-chat/  — start or resume chat (user)
# ══════════════════════════════════════════════════════════════════════════════

def test_start_chat_new_returns_201_with_is_new_true(api_client, mocker):
    chat = make_chat(chat_id=10, name="Asistente Alfa — 01/01/2025 10:00")
    mocker.patch(f"{VIEW}.assistant_service.start_chat", return_value=(chat, True))
    response = api_client.post("/api/v1/assistants/1/start-chat/", {}, format="json")
    assert response.status_code == 201
    assert response.data["is_new"] is True
    assert response.data["chat_id"] == 10


def test_start_chat_resumed_returns_200_with_is_new_false(api_client, mocker):
    chat = make_chat(chat_id=5, name="Asistente Alfa — 15/03/2025 09:30")
    mocker.patch(f"{VIEW}.assistant_service.start_chat", return_value=(chat, False))
    response = api_client.post(
        "/api/v1/assistants/1/start-chat/", {"resume": True}, format="json"
    )
    assert response.status_code == 200
    assert response.data["is_new"] is False
    assert response.data["chat_id"] == 5


def test_start_chat_response_fields(api_client, mocker):
    chat = make_chat(chat_id=7, name="Chat nombre")
    mocker.patch(f"{VIEW}.assistant_service.start_chat", return_value=(chat, True))
    response = api_client.post("/api/v1/assistants/1/start-chat/", {}, format="json")
    assert "chat_id" in response.data
    assert "chat_name" in response.data
    assert "is_new" in response.data
    assert response.data["chat_name"] == "Chat nombre"


def test_start_chat_passes_resume_false_by_default(api_client, mocker):
    svc = mocker.patch(
        f"{VIEW}.assistant_service.start_chat",
        return_value=(make_chat(), True),
    )
    api_client.post("/api/v1/assistants/1/start-chat/", {}, format="json")
    _, kwargs = svc.call_args
    assert kwargs["resume"] is False


def test_start_chat_passes_resume_true_when_provided(api_client, mocker):
    svc = mocker.patch(
        f"{VIEW}.assistant_service.start_chat",
        return_value=(make_chat(), False),
    )
    api_client.post("/api/v1/assistants/1/start-chat/", {"resume": True}, format="json")
    _, kwargs = svc.call_args
    assert kwargs["resume"] is True


def test_start_chat_passes_assistant_id_from_url(api_client, mocker):
    svc = mocker.patch(
        f"{VIEW}.assistant_service.start_chat",
        return_value=(make_chat(), True),
    )
    api_client.post("/api/v1/assistants/42/start-chat/", {}, format="json")
    _, kwargs = svc.call_args
    assert kwargs["assistant_id"] == 42


def test_start_chat_invalid_resume_returns_400(api_client, mocker):
    """A non-boolean `resume` value is rejected by the serializer."""
    mocker.patch(f"{VIEW}.assistant_service.start_chat")
    response = api_client.post(
        "/api/v1/assistants/1/start-chat/", {"resume": "maybe"}, format="json"
    )
    assert response.status_code == 400


def test_start_chat_assistant_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.start_chat",
        side_effect=AssistantNotFoundException(),
    )
    response = api_client.post("/api/v1/assistants/999/start-chat/", {}, format="json")
    assert response.status_code == 404
    assert response.data["error"] == "assistant_not_found"


def test_start_chat_inactive_assistant_returns_400(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.start_chat",
        side_effect=AssistantInactiveException(),
    )
    response = api_client.post("/api/v1/assistants/1/start-chat/", {}, format="json")
    assert response.status_code == 400
    assert response.data["error"] == "assistant_inactive"


def test_start_chat_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.assistant_service.start_chat",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.post("/api/v1/assistants/1/start-chat/", {}, format="json")
    assert response.status_code == 403


def test_start_chat_unauthenticated_returns_401(anon_client):
    response = anon_client.post("/api/v1/assistants/1/start-chat/", {}, format="json")
    assert response.status_code == 401
