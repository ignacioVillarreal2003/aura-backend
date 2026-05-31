from unittest.mock import AsyncMock

import pytest

from apps.checklist.exceptions import (
    ChecklistAccessDeniedException,
    ChecklistExportException,
    ChecklistNotFoundException,
    LLMServiceException,
)
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from core.exceptions.base import InsufficientPermissionsException
from test.conftest import make_checklist, make_checklist_section, make_checklist_item

VIEW = "apps.checklist.views"

# ── Shared payload helpers ────────────────────────────────────────────────────

_VALID_SECTIONS = [
    {
        "title": "Fase 1",
        "position": 0,
        "items": [
            {"text": "Tarea A", "is_checked": False, "notes": "", "position": 0},
        ],
    }
]


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/checklists/
# ══════════════════════════════════════════════════════════════════════════════

def test_list_checklists_returns_200_paginated(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.list_checklists", return_value=[make_checklist()])
    response = api_client.get("/api/v1/checklists/")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["id"] == 1


def test_list_checklists_empty_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.list_checklists", return_value=[])
    response = api_client.get("/api/v1/checklists/")
    assert response.status_code == 200
    assert response.data["results"] == []
    assert response.data["count"] == 0


def test_list_checklists_passes_chat_id_to_service(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.checklist_service.list_checklists", return_value=[])
    api_client.get("/api/v1/checklists/?chat_id=5")
    _, kwargs = svc.call_args
    assert kwargs["chat_id"] == 5


def test_list_checklists_ignores_non_numeric_chat_id(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.checklist_service.list_checklists", return_value=[])
    api_client.get("/api/v1/checklists/?chat_id=abc")
    _, kwargs = svc.call_args
    assert kwargs["chat_id"] is None


def test_list_checklists_ignores_negative_chat_id(api_client, mocker):
    # Negative numbers fail str.isdigit() → falls back to None
    svc = mocker.patch(f"{VIEW}.checklist_service.list_checklists", return_value=[])
    api_client.get("/api/v1/checklists/?chat_id=-1")
    _, kwargs = svc.call_args
    assert kwargs["chat_id"] is None


def test_list_checklists_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.list_checklists", side_effect=ChatNotFoundException())
    response = api_client.get("/api/v1/checklists/?chat_id=999")
    assert response.status_code == 404


def test_list_checklists_not_chat_member_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.list_checklists", side_effect=ChatAccessDeniedException())
    response = api_client.get("/api/v1/checklists/?chat_id=1")
    assert response.status_code == 403


def test_list_checklists_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.list_checklists", side_effect=InsufficientPermissionsException())
    response = api_client.get("/api/v1/checklists/")
    assert response.status_code == 403


def test_list_checklists_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/checklists/")
    assert response.status_code == 401


def test_list_checklists_response_includes_item_and_checked_counts(api_client, mocker):
    cl = make_checklist(item_count=5, checked_count=3)
    mocker.patch(f"{VIEW}.checklist_service.list_checklists", return_value=[cl])
    response = api_client.get("/api/v1/checklists/")
    result = response.data["results"][0]
    assert result["item_count"] == 5
    assert result["checked_count"] == 3


def test_list_checklists_no_sections_in_list_response(api_client, mocker):
    """List endpoint returns summary — sections must NOT be included."""
    mocker.patch(f"{VIEW}.checklist_service.list_checklists", return_value=[make_checklist()])
    response = api_client.get("/api/v1/checklists/")
    result = response.data["results"][0]
    assert "sections" not in result


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/checklists/{id}/
# ══════════════════════════════════════════════════════════════════════════════

def test_get_checklist_returns_200_with_nested_sections(api_client, mocker):
    section = make_checklist_section(items=[make_checklist_item(item_id=10, text="Verificar radio")])
    cl = make_checklist(sections=[section])
    mocker.patch(f"{VIEW}.checklist_service.get_checklist", return_value=cl)
    response = api_client.get("/api/v1/checklists/1/")
    assert response.status_code == 200
    data = response.data
    assert data["id"] == 1
    assert len(data["sections"]) == 1
    assert data["sections"][0]["title"] == "Preparación"
    assert data["sections"][0]["items"][0]["text"] == "Verificar radio"


def test_get_checklist_response_fields_are_complete(api_client, mocker):
    cl = make_checklist(source_chat_id=42)
    mocker.patch(f"{VIEW}.checklist_service.get_checklist", return_value=cl)
    response = api_client.get("/api/v1/checklists/1/")
    data = response.data
    for field in ("id", "title", "mode", "sections", "source_chat_id", "created_by", "created_at"):
        assert field in data, f"Missing field: {field}"
    assert data["source_chat_id"] == 42


def test_get_checklist_item_fields_are_complete(api_client, mocker):
    item = make_checklist_item(item_id=5, text="Test item", is_checked=True, notes="nota", position=1)
    cl = make_checklist(sections=[make_checklist_section(items=[item])])
    mocker.patch(f"{VIEW}.checklist_service.get_checklist", return_value=cl)
    response = api_client.get("/api/v1/checklists/1/")
    resp_item = response.data["sections"][0]["items"][0]
    assert resp_item["id"] == 5
    assert resp_item["text"] == "Test item"
    assert resp_item["is_checked"] is True
    assert resp_item["notes"] == "nota"
    assert resp_item["position"] == 1


def test_get_checklist_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_checklist", side_effect=ChecklistNotFoundException())
    response = api_client.get("/api/v1/checklists/999/")
    assert response.status_code == 404
    assert response.data["error"] == "checklist_not_found"


def test_get_checklist_access_denied_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_checklist", side_effect=ChecklistAccessDeniedException())
    response = api_client.get("/api/v1/checklists/1/")
    assert response.status_code == 403
    assert response.data["error"] == "checklist_access_denied"


def test_get_checklist_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_checklist", side_effect=InsufficientPermissionsException())
    response = api_client.get("/api/v1/checklists/1/")
    assert response.status_code == 403


def test_get_checklist_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/checklists/1/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /api/v1/checklists/{id}/
# ══════════════════════════════════════════════════════════════════════════════

def test_patch_title_only_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist", return_value=make_checklist(title="Nuevo"))
    response = api_client.patch("/api/v1/checklists/1/", {"title": "Nuevo"}, format="json")
    assert response.status_code == 200
    assert response.data["title"] == "Nuevo"


def test_patch_sections_only_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist", return_value=make_checklist())
    response = api_client.patch("/api/v1/checklists/1/", {"sections": _VALID_SECTIONS}, format="json")
    assert response.status_code == 200


def test_patch_title_and_sections_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist", return_value=make_checklist(title="Actualizado"))
    response = api_client.patch(
        "/api/v1/checklists/1/",
        {"title": "Actualizado", "sections": _VALID_SECTIONS},
        format="json",
    )
    assert response.status_code == 200


def test_patch_forwards_validated_data_to_service(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.checklist_service.update_checklist", return_value=make_checklist())
    api_client.patch(
        "/api/v1/checklists/3/",
        {"title": "Mi título", "sections": _VALID_SECTIONS},
        format="json",
    )
    _, kwargs = svc.call_args
    assert kwargs["checklist_id"] == 3
    assert kwargs["title"] == "Mi título"
    assert kwargs["sections"] is not None


def test_patch_empty_body_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist")
    response = api_client.patch("/api/v1/checklists/1/", {}, format="json")
    assert response.status_code == 400


def test_patch_blank_title_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist")
    response = api_client.patch("/api/v1/checklists/1/", {"title": "   "}, format="json")
    assert response.status_code == 400


def test_patch_title_exactly_500_chars_is_valid(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist", return_value=make_checklist())
    response = api_client.patch("/api/v1/checklists/1/", {"title": "x" * 500}, format="json")
    assert response.status_code == 200


def test_patch_title_over_500_chars_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist")
    response = api_client.patch("/api/v1/checklists/1/", {"title": "x" * 501}, format="json")
    assert response.status_code == 400


def test_patch_section_title_over_200_chars_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist")
    bad = [{"title": "A" * 201, "position": 0,
            "items": [{"text": "ok", "is_checked": False, "notes": "", "position": 0}]}]
    response = api_client.patch("/api/v1/checklists/1/", {"sections": bad}, format="json")
    assert response.status_code == 400


def test_patch_item_text_over_500_chars_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist")
    bad = [{"title": "S", "position": 0,
            "items": [{"text": "x" * 501, "is_checked": False, "notes": "", "position": 0}]}]
    response = api_client.patch("/api/v1/checklists/1/", {"sections": bad}, format="json")
    assert response.status_code == 400


def test_patch_item_negative_position_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist")
    bad = [{"title": "S", "position": 0,
            "items": [{"text": "item", "is_checked": False, "notes": "", "position": -1}]}]
    response = api_client.patch("/api/v1/checklists/1/", {"sections": bad}, format="json")
    assert response.status_code == 400


def test_patch_section_negative_position_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist")
    bad = [{"title": "S", "position": -1,
            "items": [{"text": "item", "is_checked": False, "notes": "", "position": 0}]}]
    response = api_client.patch("/api/v1/checklists/1/", {"sections": bad}, format="json")
    assert response.status_code == 400


def test_patch_exactly_200_items_is_valid(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist", return_value=make_checklist())
    items = [{"text": f"Item {i}", "is_checked": False, "notes": "", "position": i} for i in range(200)]
    response = api_client.patch(
        "/api/v1/checklists/1/",
        {"sections": [{"title": "S", "position": 0, "items": items}]},
        format="json",
    )
    assert response.status_code == 200


def test_patch_201_items_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist")
    items = [{"text": f"Item {i}", "is_checked": False, "notes": "", "position": i} for i in range(201)]
    response = api_client.patch(
        "/api/v1/checklists/1/",
        {"sections": [{"title": "S", "position": 0, "items": items}]},
        format="json",
    )
    assert response.status_code == 400


def test_patch_items_split_across_sections_exceed_200_returns_400(api_client, mocker):
    """201 items split across two sections still violates the 200-item limit."""
    mocker.patch(f"{VIEW}.checklist_service.update_checklist")
    items_a = [{"text": f"A{i}", "is_checked": False, "notes": "", "position": i} for i in range(101)]
    items_b = [{"text": f"B{i}", "is_checked": False, "notes": "", "position": i} for i in range(100)]
    sections = [
        {"title": "A", "position": 0, "items": items_a},
        {"title": "B", "position": 1, "items": items_b},
    ]
    response = api_client.patch("/api/v1/checklists/1/", {"sections": sections}, format="json")
    assert response.status_code == 400


def test_patch_item_blank_notes_is_allowed(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist", return_value=make_checklist())
    sections = [{"title": "S", "position": 0,
                 "items": [{"text": "tarea", "is_checked": False, "notes": "", "position": 0}]}]
    response = api_client.patch("/api/v1/checklists/1/", {"sections": sections}, format="json")
    assert response.status_code == 200


def test_patch_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist", side_effect=ChecklistNotFoundException())
    response = api_client.patch("/api/v1/checklists/999/", {"title": "X"}, format="json")
    assert response.status_code == 404
    assert response.data["error"] == "checklist_not_found"


def test_patch_access_denied_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist", side_effect=ChecklistAccessDeniedException())
    response = api_client.patch("/api/v1/checklists/1/", {"title": "X"}, format="json")
    assert response.status_code == 403
    assert response.data["error"] == "checklist_access_denied"


def test_patch_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.update_checklist", side_effect=InsufficientPermissionsException())
    response = api_client.patch("/api/v1/checklists/1/", {"title": "X"}, format="json")
    assert response.status_code == 403


def test_patch_unauthenticated_returns_401(anon_client):
    response = anon_client.patch("/api/v1/checklists/1/", {"title": "X"}, format="json")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /api/v1/checklists/{id}/
# ══════════════════════════════════════════════════════════════════════════════

def test_delete_checklist_returns_204(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.delete_checklist")
    response = api_client.delete("/api/v1/checklists/1/")
    assert response.status_code == 204
    assert not response.content


def test_delete_checklist_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.delete_checklist", side_effect=ChecklistNotFoundException())
    response = api_client.delete("/api/v1/checklists/999/")
    assert response.status_code == 404
    assert response.data["error"] == "checklist_not_found"


def test_delete_checklist_non_member_returns_403(api_client, mocker):
    """User who is neither the creator nor an active chat member cannot delete."""
    mocker.patch(f"{VIEW}.checklist_service.delete_checklist", side_effect=ChecklistAccessDeniedException())
    response = api_client.delete("/api/v1/checklists/1/")
    assert response.status_code == 403
    assert response.data["error"] == "checklist_access_denied"


def test_delete_checklist_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.delete_checklist", side_effect=InsufficientPermissionsException())
    response = api_client.delete("/api/v1/checklists/1/")
    assert response.status_code == 403


def test_delete_checklist_unauthenticated_returns_401(anon_client):
    response = anon_client.delete("/api/v1/checklists/1/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/checklists/{id}/export/pdf/
# ══════════════════════════════════════════════════════════════════════════════

def test_export_pdf_returns_200_application_pdf(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_own_checklist", return_value=make_checklist())
    mocker.patch(f"{VIEW}.generate_checklist_pdf", return_value=b"%PDF-1.4 fake")
    response = api_client.get("/api/v1/checklists/1/export/pdf/")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"


def test_export_pdf_content_disposition_is_attachment(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_own_checklist", return_value=make_checklist(title="Mi lista"))
    mocker.patch(f"{VIEW}.generate_checklist_pdf", return_value=b"%PDF-1.4 fake")
    response = api_client.get("/api/v1/checklists/1/export/pdf/")
    disp = response["Content-Disposition"]
    assert "attachment" in disp
    assert "checklist_" in disp
    assert ".pdf" in disp


def test_export_pdf_filename_sanitizes_special_chars(api_client, mocker):
    mocker.patch(
        f"{VIEW}.checklist_service.get_own_checklist",
        return_value=make_checklist(title="Lista & operaciones!"),
    )
    mocker.patch(f"{VIEW}.generate_checklist_pdf", return_value=b"%PDF fake")
    response = api_client.get("/api/v1/checklists/1/export/pdf/")
    disp = response["Content-Disposition"]
    assert "&" not in disp
    assert "!" not in disp


def test_export_pdf_title_truncated_to_60_chars_in_filename(api_client, mocker):
    mocker.patch(
        f"{VIEW}.checklist_service.get_own_checklist",
        return_value=make_checklist(title="A" * 100),
    )
    mocker.patch(f"{VIEW}.generate_checklist_pdf", return_value=b"%PDF fake")
    response = api_client.get("/api/v1/checklists/1/export/pdf/")
    disp = response["Content-Disposition"]
    # After truncation and re-sub the filename slug is ≤60 chars
    filename = disp.split('filename="')[1].rstrip('"')
    slug = filename.replace("checklist_", "").replace(".pdf", "")
    assert len(slug) <= 60


def test_export_pdf_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_own_checklist", side_effect=ChecklistNotFoundException())
    response = api_client.get("/api/v1/checklists/999/export/pdf/")
    assert response.status_code == 404


def test_export_pdf_access_denied_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_own_checklist", side_effect=ChecklistAccessDeniedException())
    response = api_client.get("/api/v1/checklists/1/export/pdf/")
    assert response.status_code == 403


def test_export_pdf_export_failure_returns_500(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_own_checklist", return_value=make_checklist())
    mocker.patch(f"{VIEW}.generate_checklist_pdf", side_effect=ChecklistExportException())
    response = api_client.get("/api/v1/checklists/1/export/pdf/")
    assert response.status_code == 500
    assert response.data["error"] == "checklist_export_failed"


def test_export_pdf_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_own_checklist", side_effect=InsufficientPermissionsException())
    response = api_client.get("/api/v1/checklists/1/export/pdf/")
    assert response.status_code == 403


def test_export_pdf_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/checklists/1/export/pdf/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/checklists/{id}/export/markdown/
# ══════════════════════════════════════════════════════════════════════════════

def test_export_markdown_returns_200_text_markdown(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_own_checklist", return_value=make_checklist())
    mocker.patch(f"{VIEW}.generate_checklist_markdown", return_value="# Checklist\n")
    response = api_client.get("/api/v1/checklists/1/export/markdown/")
    assert response.status_code == 200
    assert "markdown" in response["Content-Type"]


def test_export_markdown_content_disposition_ends_with_md(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_own_checklist", return_value=make_checklist())
    mocker.patch(f"{VIEW}.generate_checklist_markdown", return_value="# Checklist\n")
    response = api_client.get("/api/v1/checklists/1/export/markdown/")
    disp = response["Content-Disposition"]
    assert "attachment" in disp
    assert disp.endswith('.md"')


def test_export_markdown_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_own_checklist", side_effect=ChecklistNotFoundException())
    response = api_client.get("/api/v1/checklists/999/export/markdown/")
    assert response.status_code == 404


def test_export_markdown_access_denied_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_own_checklist", side_effect=ChecklistAccessDeniedException())
    response = api_client.get("/api/v1/checklists/1/export/markdown/")
    assert response.status_code == 403


def test_export_markdown_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_own_checklist", side_effect=InsufficientPermissionsException())
    response = api_client.get("/api/v1/checklists/1/export/markdown/")
    assert response.status_code == 403


def test_export_markdown_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/checklists/1/export/markdown/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/checklists/generate/
# ══════════════════════════════════════════════════════════════════════════════

def test_generate_returns_201_with_checklist_messages_fragments(api_client, mocker):
    messages = [{"role": "human", "content": "texto"}, {"role": "assistant", "content": "resp"}]
    fragments = [{"content": "fragmento", "document": {}}]
    mocker.patch(
        f"{VIEW}.checklist_service.generate_checklist",
        new_callable=AsyncMock,
        return_value=(make_checklist(), messages, fragments),
    )
    response = api_client.post(
        "/api/v1/checklists/generate/",
        {"mode": "direct", "message": "Crea una checklist de mantenimiento"},
        format="json",
    )
    assert response.status_code == 201
    assert "checklist" in response.data
    assert "messages" in response.data
    assert "fragments" in response.data
    assert response.data["checklist"]["id"] == 1
    assert len(response.data["messages"]) == 2


def test_generate_rag_mode_accepted(api_client, mocker):
    mocker.patch(
        f"{VIEW}.checklist_service.generate_checklist",
        new_callable=AsyncMock,
        return_value=(make_checklist(mode="rag"), [], []),
    )
    response = api_client.post(
        "/api/v1/checklists/generate/",
        {"mode": "rag", "message": "Checklist con documentos"},
        format="json",
    )
    assert response.status_code == 201


def test_generate_with_chat_id_passes_it_to_service(api_client, mocker):
    svc = mocker.patch(
        f"{VIEW}.checklist_service.generate_checklist",
        new_callable=AsyncMock,
        return_value=(make_checklist(source_chat_id=7), [], []),
    )
    api_client.post(
        "/api/v1/checklists/generate/",
        {"mode": "direct", "message": "Checklist", "chat_id": 7},
        format="json",
    )
    _, kwargs = svc.call_args
    assert kwargs["chat_id"] == 7


def test_generate_missing_mode_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.generate_checklist", new_callable=AsyncMock)
    response = api_client.post(
        "/api/v1/checklists/generate/",
        {"message": "Crea una checklist"},
        format="json",
    )
    assert response.status_code == 400


def test_generate_invalid_mode_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.generate_checklist", new_callable=AsyncMock)
    response = api_client.post(
        "/api/v1/checklists/generate/",
        {"mode": "turbo", "message": "Checklist"},
        format="json",
    )
    assert response.status_code == 400


def test_generate_missing_message_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.generate_checklist", new_callable=AsyncMock)
    response = api_client.post(
        "/api/v1/checklists/generate/",
        {"mode": "direct"},
        format="json",
    )
    assert response.status_code == 400


def test_generate_blank_message_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.generate_checklist", new_callable=AsyncMock)
    response = api_client.post(
        "/api/v1/checklists/generate/",
        {"mode": "direct", "message": ""},
        format="json",
    )
    assert response.status_code == 400


def test_generate_message_over_4000_chars_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.generate_checklist", new_callable=AsyncMock)
    response = api_client.post(
        "/api/v1/checklists/generate/",
        {"mode": "direct", "message": "x" * 4001},
        format="json",
    )
    assert response.status_code == 400


def test_generate_message_exactly_4000_chars_is_valid(api_client, mocker):
    mocker.patch(
        f"{VIEW}.checklist_service.generate_checklist",
        new_callable=AsyncMock,
        return_value=(make_checklist(), [], []),
    )
    response = api_client.post(
        "/api/v1/checklists/generate/",
        {"mode": "direct", "message": "x" * 4000},
        format="json",
    )
    assert response.status_code == 201


def test_generate_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{VIEW}.checklist_service.generate_checklist",
        new_callable=AsyncMock,
        side_effect=ChatNotFoundException(),
    )
    response = api_client.post(
        "/api/v1/checklists/generate/",
        {"mode": "direct", "message": "Checklist", "chat_id": 999},
        format="json",
    )
    assert response.status_code == 404


def test_generate_not_chat_member_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.checklist_service.generate_checklist",
        new_callable=AsyncMock,
        side_effect=ChatAccessDeniedException(),
    )
    response = api_client.post(
        "/api/v1/checklists/generate/",
        {"mode": "direct", "message": "Checklist", "chat_id": 1},
        format="json",
    )
    assert response.status_code == 403


def test_generate_llm_failure_returns_502(api_client, mocker):
    mocker.patch(
        f"{VIEW}.checklist_service.generate_checklist",
        new_callable=AsyncMock,
        side_effect=LLMServiceException(),
    )
    response = api_client.post(
        "/api/v1/checklists/generate/",
        {"mode": "direct", "message": "Checklist"},
        format="json",
    )
    assert response.status_code == 502
    assert response.data["error"] == "llm_service_error"


def test_generate_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.checklist_service.generate_checklist",
        new_callable=AsyncMock,
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.post(
        "/api/v1/checklists/generate/",
        {"mode": "direct", "message": "Checklist"},
        format="json",
    )
    assert response.status_code == 403


def test_generate_unauthenticated_returns_401(anon_client):
    response = anon_client.post(
        "/api/v1/checklists/generate/",
        {"mode": "direct", "message": "Checklist"},
        format="json",
    )
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/checklists/manage/  (admin)
# ══════════════════════════════════════════════════════════════════════════════

def test_manage_list_returns_200_with_all_checklists(api_client, mocker):
    cls = [make_checklist(cl_id=1), make_checklist(cl_id=2, title="Otra", created_by=99)]
    mocker.patch(f"{VIEW}.checklist_service.list_all_checklists", return_value=cls)
    response = api_client.get("/api/v1/checklists/manage/")
    assert response.status_code == 200
    assert len(response.data["results"]) == 2


def test_manage_list_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.checklist_service.list_all_checklists",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/checklists/manage/")
    assert response.status_code == 403


def test_manage_list_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/checklists/manage/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/checklists/manage/{id}/export/pdf/  (admin)
# ══════════════════════════════════════════════════════════════════════════════

def test_manage_export_pdf_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_checklist_admin_export", return_value=make_checklist())
    mocker.patch(f"{VIEW}.generate_checklist_pdf", return_value=b"%PDF-1.4 admin")
    response = api_client.get("/api/v1/checklists/manage/1/export/pdf/")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert "attachment" in response["Content-Disposition"]


def test_manage_export_pdf_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{VIEW}.checklist_service.get_checklist_admin_export",
        side_effect=ChecklistNotFoundException(),
    )
    response = api_client.get("/api/v1/checklists/manage/999/export/pdf/")
    assert response.status_code == 404


def test_manage_export_pdf_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.checklist_service.get_checklist_admin_export",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/checklists/manage/1/export/pdf/")
    assert response.status_code == 403


def test_manage_export_pdf_export_failure_returns_500(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_checklist_admin_export", return_value=make_checklist())
    mocker.patch(f"{VIEW}.generate_checklist_pdf", side_effect=ChecklistExportException())
    response = api_client.get("/api/v1/checklists/manage/1/export/pdf/")
    assert response.status_code == 500
    assert response.data["error"] == "checklist_export_failed"


def test_manage_export_pdf_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/checklists/manage/1/export/pdf/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/checklists/manage/{id}/export/markdown/  (admin)
# ══════════════════════════════════════════════════════════════════════════════

def test_manage_export_markdown_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.checklist_service.get_checklist_admin_export", return_value=make_checklist())
    mocker.patch(f"{VIEW}.generate_checklist_markdown", return_value="# Admin CL\n")
    response = api_client.get("/api/v1/checklists/manage/1/export/markdown/")
    assert response.status_code == 200
    assert "markdown" in response["Content-Type"]
    assert response["Content-Disposition"].endswith('.md"')


def test_manage_export_markdown_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{VIEW}.checklist_service.get_checklist_admin_export",
        side_effect=ChecklistNotFoundException(),
    )
    response = api_client.get("/api/v1/checklists/manage/999/export/markdown/")
    assert response.status_code == 404


def test_manage_export_markdown_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.checklist_service.get_checklist_admin_export",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/checklists/manage/1/export/markdown/")
    assert response.status_code == 403


def test_manage_export_markdown_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/checklists/manage/1/export/markdown/")
    assert response.status_code == 401
