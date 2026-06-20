"""
Unit tests for report endpoints — all service calls are mocked.

Endpoints covered:
  GET    /api/v1/reports/                               list user reports
  GET    /api/v1/reports/{id}/                          get report
  PATCH  /api/v1/reports/{id}/                          update report
  DELETE /api/v1/reports/{id}/                          delete report
  GET    /api/v1/reports/{id}/export/pdf/               export PDF
  GET    /api/v1/reports/{id}/export/markdown/          export Markdown
  POST   /api/v1/reports/generate/                      generate with LLM
  GET    /api/v1/reports/manage/                        list all (admin)
  GET    /api/v1/reports/manage/{id}/export/pdf/        export any PDF (admin)
  GET    /api/v1/reports/manage/{id}/export/markdown/   export any Markdown (admin)
"""
import contextlib
from unittest.mock import AsyncMock

import pytest

from apps.artifact_report.exceptions import (
    ReportAccessDeniedException,
    ReportExportException,
    ReportNotFoundException,
    LLMServiceException,
)
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from core.exceptions.base import InsufficientPermissionsException
from test.conftest import make_report

VIEW = "apps.artifact_report.views"


def _patch_generate_deps(mocker, *, is_contributor=True, rate_ok=True):
    """The generate view now validates chat membership, rate limit and holds the AI
    reply lock before calling the service. Patch those guards for happy-path tests."""
    mocker.patch(f"{VIEW}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{VIEW}.membership_repository.is_active_contributor", return_value=is_contributor)
    mocker.patch(f"{VIEW}.check_artifact_rate_limit", return_value=rate_ok)

    @contextlib.asynccontextmanager
    async def _noop_lock(chat_id):
        yield

    mocker.patch(f"{VIEW}.ai_reply_lock_guard", _noop_lock)


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/reports/
# ══════════════════════════════════════════════════════════════════════════════

def test_list_reports_returns_200_paginated(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.list_reports", return_value=[make_report()])
    response = api_client.get("/api/v1/reports/?chat_id=5")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["id"] == 1


def test_list_reports_empty_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.list_reports", return_value=[])
    response = api_client.get("/api/v1/reports/?chat_id=5")
    assert response.status_code == 200
    assert response.data["results"] == []
    assert response.data["count"] == 0


def test_list_reports_passes_chat_id_to_service(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.report_service.list_reports", return_value=[])
    api_client.get("/api/v1/reports/?chat_id=5")
    _, kwargs = svc.call_args
    assert kwargs["chat_id"] == 5


def test_list_reports_non_numeric_chat_id_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.list_reports", return_value=[])
    response = api_client.get("/api/v1/reports/?chat_id=abc")
    assert response.status_code == 400


def test_list_reports_missing_chat_id_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.list_reports", return_value=[])
    response = api_client.get("/api/v1/reports/")
    assert response.status_code == 400


def test_list_reports_passes_type_filter_to_service(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.report_service.list_reports", return_value=[])
    api_client.get("/api/v1/reports/?type=SITREP&chat_id=5")
    _, kwargs = svc.call_args
    assert kwargs["report_type"] == "SITREP"


def test_list_reports_empty_type_param_passes_none(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.report_service.list_reports", return_value=[])
    api_client.get("/api/v1/reports/?type=&chat_id=5")
    _, kwargs = svc.call_args
    assert kwargs["report_type"] is None


def test_list_reports_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.list_reports", side_effect=ChatNotFoundException())
    response = api_client.get("/api/v1/reports/?chat_id=999")
    assert response.status_code == 404


def test_list_reports_not_chat_member_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.list_reports", side_effect=ChatAccessDeniedException())
    response = api_client.get("/api/v1/reports/?chat_id=1")
    assert response.status_code == 403


def test_list_reports_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.list_reports", side_effect=InsufficientPermissionsException())
    response = api_client.get("/api/v1/reports/?chat_id=1")
    assert response.status_code == 403


def test_list_reports_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/reports/")
    assert response.status_code == 401


def test_list_reports_no_content_in_list_response(api_client, mocker):
    """List endpoint returns summary — content must NOT be included."""
    mocker.patch(f"{VIEW}.report_service.list_reports", return_value=[make_report()])
    response = api_client.get("/api/v1/reports/?chat_id=5")
    result = response.data["results"][0]
    assert "content" not in result


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/reports/{id}/
# ══════════════════════════════════════════════════════════════════════════════

def test_get_report_returns_200_with_all_fields(api_client, mocker):
    rp = make_report(report_id=1, report_type="SITREP", content="Contenido detallado", source_chat_id=42)
    mocker.patch(f"{VIEW}.report_service.get_report", return_value=rp)
    response = api_client.get("/api/v1/reports/1/")
    assert response.status_code == 200
    data = response.data
    assert data["id"] == 1
    assert data["type"] == "SITREP"
    assert data["content"] == "Contenido detallado"
    assert data["source_chat_id"] == 42


def test_get_report_response_fields_are_complete(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_report", return_value=make_report())
    response = api_client.get("/api/v1/reports/1/")
    data = response.data
    for field in ("id", "type", "title", "content", "retrieve_context", "process_documents", "document_ids", "source_chat_id", "created_by", "created_at"):
        assert field in data, f"Missing field: {field}"


def test_get_report_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_report", side_effect=ReportNotFoundException())
    response = api_client.get("/api/v1/reports/999/")
    assert response.status_code == 404
    assert response.data["error"] == "report_not_found"


def test_get_report_access_denied_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_report", side_effect=ReportAccessDeniedException())
    response = api_client.get("/api/v1/reports/1/")
    assert response.status_code == 403
    assert response.data["error"] == "report_access_denied"


def test_get_report_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_report", side_effect=InsufficientPermissionsException())
    response = api_client.get("/api/v1/reports/1/")
    assert response.status_code == 403


def test_get_report_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/reports/1/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /api/v1/reports/{id}/
# ══════════════════════════════════════════════════════════════════════════════

def test_delete_report_returns_204(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.delete_report")
    response = api_client.delete("/api/v1/reports/1/")
    assert response.status_code == 204
    assert not response.content


def test_delete_report_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.delete_report", side_effect=ReportNotFoundException())
    response = api_client.delete("/api/v1/reports/999/")
    assert response.status_code == 404
    assert response.data["error"] == "report_not_found"


def test_delete_report_access_denied_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.delete_report", side_effect=ReportAccessDeniedException())
    response = api_client.delete("/api/v1/reports/1/")
    assert response.status_code == 403
    assert response.data["error"] == "report_access_denied"


def test_delete_report_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.delete_report", side_effect=InsufficientPermissionsException())
    response = api_client.delete("/api/v1/reports/1/")
    assert response.status_code == 403


def test_delete_report_unauthenticated_returns_401(anon_client):
    response = anon_client.delete("/api/v1/reports/1/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/reports/{id}/export/pdf/
# ══════════════════════════════════════════════════════════════════════════════

def test_export_pdf_returns_200_application_pdf(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_own_report", return_value=make_report())
    mocker.patch(f"{VIEW}.generate_report_pdf", return_value=b"%PDF-1.4 fake")
    response = api_client.get("/api/v1/reports/1/export/pdf/")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"


def test_export_pdf_content_disposition_is_attachment(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_own_report", return_value=make_report(title="Mi informe"))
    mocker.patch(f"{VIEW}.generate_report_pdf", return_value=b"%PDF-1.4 fake")
    response = api_client.get("/api/v1/reports/1/export/pdf/")
    disp = response["Content-Disposition"]
    assert "attachment" in disp
    assert ".pdf" in disp


def test_export_pdf_filename_includes_report_type(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_own_report", return_value=make_report(report_type="SITREP"))
    mocker.patch(f"{VIEW}.generate_report_pdf", return_value=b"%PDF fake")
    response = api_client.get("/api/v1/reports/1/export/pdf/")
    disp = response["Content-Disposition"]
    assert "SITREP" in disp


def test_export_pdf_filename_sanitizes_special_chars(api_client, mocker):
    mocker.patch(
        f"{VIEW}.report_service.get_own_report",
        return_value=make_report(title="Informe & operaciones!"),
    )
    mocker.patch(f"{VIEW}.generate_report_pdf", return_value=b"%PDF fake")
    response = api_client.get("/api/v1/reports/1/export/pdf/")
    disp = response["Content-Disposition"]
    assert "&" not in disp
    assert "!" not in disp


def test_export_pdf_title_truncated_to_60_chars_in_filename(api_client, mocker):
    mocker.patch(
        f"{VIEW}.report_service.get_own_report",
        return_value=make_report(title="A" * 100),
    )
    mocker.patch(f"{VIEW}.generate_report_pdf", return_value=b"%PDF fake")
    response = api_client.get("/api/v1/reports/1/export/pdf/")
    disp = response["Content-Disposition"]
    filename = disp.split('filename="')[1].rstrip('"')
    slug = filename.replace("SITREP_", "").replace(".pdf", "")
    assert len(slug) <= 60


def test_export_pdf_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_own_report", side_effect=ReportNotFoundException())
    response = api_client.get("/api/v1/reports/999/export/pdf/")
    assert response.status_code == 404


def test_export_pdf_access_denied_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_own_report", side_effect=ReportAccessDeniedException())
    response = api_client.get("/api/v1/reports/1/export/pdf/")
    assert response.status_code == 403


def test_export_pdf_export_failure_returns_500(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_own_report", return_value=make_report())
    mocker.patch(f"{VIEW}.generate_report_pdf", side_effect=ReportExportException())
    response = api_client.get("/api/v1/reports/1/export/pdf/")
    assert response.status_code == 500
    assert response.data["error"] == "report_export_failed"


def test_export_pdf_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_own_report", side_effect=InsufficientPermissionsException())
    response = api_client.get("/api/v1/reports/1/export/pdf/")
    assert response.status_code == 403


def test_export_pdf_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/reports/1/export/pdf/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/reports/{id}/export/markdown/
# ══════════════════════════════════════════════════════════════════════════════

def test_export_markdown_returns_200_text_markdown(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_own_report", return_value=make_report())
    mocker.patch(f"{VIEW}.generate_report_markdown", return_value="# SITREP\n")
    response = api_client.get("/api/v1/reports/1/export/markdown/")
    assert response.status_code == 200
    assert "markdown" in response["Content-Type"]


def test_export_markdown_content_disposition_ends_with_md(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_own_report", return_value=make_report())
    mocker.patch(f"{VIEW}.generate_report_markdown", return_value="# SITREP\n")
    response = api_client.get("/api/v1/reports/1/export/markdown/")
    disp = response["Content-Disposition"]
    assert "attachment" in disp
    assert disp.endswith('.md"')


def test_export_markdown_filename_includes_report_type(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_own_report", return_value=make_report(report_type="INTSUM"))
    mocker.patch(f"{VIEW}.generate_report_markdown", return_value="# INTSUM\n")
    response = api_client.get("/api/v1/reports/1/export/markdown/")
    disp = response["Content-Disposition"]
    assert "INTSUM" in disp


def test_export_markdown_not_found_returns_404(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_own_report", side_effect=ReportNotFoundException())
    response = api_client.get("/api/v1/reports/999/export/markdown/")
    assert response.status_code == 404


def test_export_markdown_access_denied_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_own_report", side_effect=ReportAccessDeniedException())
    response = api_client.get("/api/v1/reports/1/export/markdown/")
    assert response.status_code == 403


def test_export_markdown_no_permission_returns_403(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_own_report", side_effect=InsufficientPermissionsException())
    response = api_client.get("/api/v1/reports/1/export/markdown/")
    assert response.status_code == 403


def test_export_markdown_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/reports/1/export/markdown/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/reports/generate/
# ══════════════════════════════════════════════════════════════════════════════

def test_generate_returns_201_with_report_messages_fragments(api_client, mocker):
    messages = [{"role": "human", "content": "texto"}, {"role": "assistant", "content": "resp"}]
    fragments = [{"content": "fragmento", "document": {}}]
    mocker.patch(
        f"{VIEW}.report_service.generate_report",
        new_callable=AsyncMock,
        return_value=(make_report(), messages, fragments),
    )
    _patch_generate_deps(mocker)
    response = api_client.post(
        "/api/v1/reports/generate/",
        {"type": "SITREP", "mode": "direct", "message": "Genera un informe de situación", "chat_id": 1},
        format="json",
    )
    assert response.status_code == 201
    assert "report" in response.data
    assert "messages" in response.data
    assert "fragments" in response.data
    assert response.data["report"]["id"] == 1
    assert len(response.data["messages"]) == 2


def test_generate_rag_mode_accepted(api_client, mocker):
    mocker.patch(
        f"{VIEW}.report_service.generate_report",
        new_callable=AsyncMock,
        return_value=(make_report(mode="rag"), [], []),
    )
    _patch_generate_deps(mocker)
    response = api_client.post(
        "/api/v1/reports/generate/",
        {"type": "INTSUM", "mode": "rag", "message": "Informe con documentos", "chat_id": 1},
        format="json",
    )
    assert response.status_code == 201


def test_generate_all_report_types_accepted(api_client, mocker):
    for report_type in ("SITREP", "INTSUM", "OPORD"):
        mocker.patch(
            f"{VIEW}.report_service.generate_report",
            new_callable=AsyncMock,
            return_value=(make_report(report_type=report_type), [], []),
        )
        _patch_generate_deps(mocker)
        response = api_client.post(
            "/api/v1/reports/generate/",
            {"type": report_type, "mode": "direct", "message": "Informe", "chat_id": 1},
            format="json",
        )
        assert response.status_code == 201, f"Expected 201 for type={report_type}"


def test_generate_with_chat_id_passes_it_to_service(api_client, mocker):
    svc = mocker.patch(
        f"{VIEW}.report_service.generate_report",
        new_callable=AsyncMock,
        return_value=(make_report(source_chat_id=7), [], []),
    )
    _patch_generate_deps(mocker)
    api_client.post(
        "/api/v1/reports/generate/",
        {"type": "SITREP", "mode": "direct", "message": "Informe", "chat_id": 7},
        format="json",
    )
    _, kwargs = svc.call_args
    assert kwargs["chat_id"] == 7


def test_generate_missing_type_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.generate_report", new_callable=AsyncMock)
    response = api_client.post(
        "/api/v1/reports/generate/",
        {"mode": "direct", "message": "Informe"},
        format="json",
    )
    assert response.status_code == 400


def test_generate_invalid_type_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.generate_report", new_callable=AsyncMock)
    response = api_client.post(
        "/api/v1/reports/generate/",
        {"type": "INVALID", "mode": "direct", "message": "Informe"},
        format="json",
    )
    assert response.status_code == 400


def test_generate_missing_mode_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.generate_report", new_callable=AsyncMock)
    response = api_client.post(
        "/api/v1/reports/generate/",
        {"type": "SITREP", "message": "Informe"},
        format="json",
    )
    assert response.status_code == 400


def test_generate_invalid_mode_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.generate_report", new_callable=AsyncMock)
    response = api_client.post(
        "/api/v1/reports/generate/",
        {"type": "SITREP", "mode": "turbo", "message": "Informe"},
        format="json",
    )
    assert response.status_code == 400


def test_generate_missing_message_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.generate_report", new_callable=AsyncMock)
    response = api_client.post(
        "/api/v1/reports/generate/",
        {"type": "SITREP", "mode": "direct"},
        format="json",
    )
    assert response.status_code == 400


def test_generate_blank_message_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.generate_report", new_callable=AsyncMock)
    response = api_client.post(
        "/api/v1/reports/generate/",
        {"type": "SITREP", "mode": "direct", "message": ""},
        format="json",
    )
    assert response.status_code == 400


def test_generate_message_over_4000_chars_returns_400(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.generate_report", new_callable=AsyncMock)
    response = api_client.post(
        "/api/v1/reports/generate/",
        {"type": "SITREP", "mode": "direct", "message": "x" * 4001},
        format="json",
    )
    assert response.status_code == 400


def test_generate_message_exactly_4000_chars_is_valid(api_client, mocker):
    mocker.patch(
        f"{VIEW}.report_service.generate_report",
        new_callable=AsyncMock,
        return_value=(make_report(), [], []),
    )
    _patch_generate_deps(mocker)
    response = api_client.post(
        "/api/v1/reports/generate/",
        {"type": "SITREP", "mode": "direct", "message": "x" * 4000, "chat_id": 1},
        format="json",
    )
    assert response.status_code == 201


def test_generate_chat_not_found_returns_404(api_client, mocker):
    # The view looks the chat up itself before calling the service.
    mocker.patch(f"{VIEW}.chat_repository.get_by_id", return_value=None)
    response = api_client.post(
        "/api/v1/reports/generate/",
        {"type": "SITREP", "mode": "direct", "message": "Informe", "chat_id": 999},
        format="json",
    )
    assert response.status_code == 404


def test_generate_not_chat_contributor_returns_403(api_client, mocker):
    """Reader role cannot generate reports with a chat_id."""
    _patch_generate_deps(mocker, is_contributor=False)
    response = api_client.post(
        "/api/v1/reports/generate/",
        {"type": "SITREP", "mode": "direct", "message": "Informe", "chat_id": 1},
        format="json",
    )
    assert response.status_code == 403


def test_generate_llm_failure_returns_502(api_client, mocker):
    mocker.patch(
        f"{VIEW}.report_service.generate_report",
        new_callable=AsyncMock,
        side_effect=LLMServiceException(),
    )
    _patch_generate_deps(mocker)
    response = api_client.post(
        "/api/v1/reports/generate/",
        {"type": "SITREP", "mode": "direct", "message": "Informe", "chat_id": 1},
        format="json",
    )
    assert response.status_code == 502
    assert response.data["error"] == "llm_service_error"


def test_generate_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.report_service.generate_report",
        new_callable=AsyncMock,
        side_effect=InsufficientPermissionsException(),
    )
    _patch_generate_deps(mocker)
    response = api_client.post(
        "/api/v1/reports/generate/",
        {"type": "SITREP", "mode": "direct", "message": "Informe", "chat_id": 1},
        format="json",
    )
    assert response.status_code == 403


def test_generate_unauthenticated_returns_401(anon_client):
    response = anon_client.post(
        "/api/v1/reports/generate/",
        {"type": "SITREP", "mode": "direct", "message": "Informe"},
        format="json",
    )
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/reports/manage/  (admin)
# ══════════════════════════════════════════════════════════════════════════════

def test_manage_list_returns_200_with_all_reports(api_client, mocker):
    reports = [make_report(report_id=1), make_report(report_id=2, created_by=99)]
    mocker.patch(f"{VIEW}.report_service.list_all_reports", return_value=reports)
    response = api_client.get("/api/v1/reports/manage/")
    assert response.status_code == 200
    assert len(response.data["results"]) == 2


def test_manage_list_passes_type_filter_to_service(api_client, mocker):
    svc = mocker.patch(f"{VIEW}.report_service.list_all_reports", return_value=[])
    api_client.get("/api/v1/reports/manage/?type=OPORD")
    _, kwargs = svc.call_args
    assert kwargs["report_type"] == "OPORD"


def test_manage_list_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.report_service.list_all_reports",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/reports/manage/")
    assert response.status_code == 403


def test_manage_list_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/reports/manage/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/reports/manage/{id}/export/pdf/  (admin)
# ══════════════════════════════════════════════════════════════════════════════

def test_manage_export_pdf_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_report_admin_export", return_value=make_report())
    mocker.patch(f"{VIEW}.generate_report_pdf", return_value=b"%PDF-1.4 admin")
    response = api_client.get("/api/v1/reports/manage/1/export/pdf/")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert "attachment" in response["Content-Disposition"]


def test_manage_export_pdf_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{VIEW}.report_service.get_report_admin_export",
        side_effect=ReportNotFoundException(),
    )
    response = api_client.get("/api/v1/reports/manage/999/export/pdf/")
    assert response.status_code == 404


def test_manage_export_pdf_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.report_service.get_report_admin_export",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/reports/manage/1/export/pdf/")
    assert response.status_code == 403


def test_manage_export_pdf_export_failure_returns_500(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_report_admin_export", return_value=make_report())
    mocker.patch(f"{VIEW}.generate_report_pdf", side_effect=ReportExportException())
    response = api_client.get("/api/v1/reports/manage/1/export/pdf/")
    assert response.status_code == 500
    assert response.data["error"] == "report_export_failed"


def test_manage_export_pdf_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/reports/manage/1/export/pdf/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/reports/manage/{id}/export/markdown/  (admin)
# ══════════════════════════════════════════════════════════════════════════════

def test_manage_export_markdown_returns_200(api_client, mocker):
    mocker.patch(f"{VIEW}.report_service.get_report_admin_export", return_value=make_report())
    mocker.patch(f"{VIEW}.generate_report_markdown", return_value="# Admin Report\n")
    response = api_client.get("/api/v1/reports/manage/1/export/markdown/")
    assert response.status_code == 200
    assert "markdown" in response["Content-Type"]
    assert response["Content-Disposition"].endswith('.md"')


def test_manage_export_markdown_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{VIEW}.report_service.get_report_admin_export",
        side_effect=ReportNotFoundException(),
    )
    response = api_client.get("/api/v1/reports/manage/999/export/markdown/")
    assert response.status_code == 404


def test_manage_export_markdown_no_permission_returns_403(api_client, mocker):
    mocker.patch(
        f"{VIEW}.report_service.get_report_admin_export",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/reports/manage/1/export/markdown/")
    assert response.status_code == 403


def test_manage_export_markdown_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/reports/manage/1/export/markdown/")
    assert response.status_code == 401
