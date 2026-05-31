from unittest.mock import AsyncMock

import pytest

from apps.report.exceptions import (
    LLMServiceException,
    ReportAccessDeniedException,
    ReportNotFoundException,
)
from apps.report.services.report_service import ReportService, _auto_title
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import ReportGenerateResult
from test.conftest import make_message, make_report, make_user

SVC = "apps.report.services.report_service"

service = ReportService()


def _patch_access(mocker, *, report, is_member=False, is_contributor=False):
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.report_repository.get_by_id", return_value=report)
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=is_member)
    mocker.patch(f"{SVC}.membership_repository.is_active_contributor", return_value=is_contributor)


# ══════════════════════════════════════════════════════════════════════════════
# get_report — any active member (reader OK)
# ══════════════════════════════════════════════════════════════════════════════

def test_get_report_creator_always_has_access(mocker):
    user = make_user(user_id=1)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, report=rp)
    result = service.get_report(user, 1)
    assert result is rp


def test_get_report_active_member_has_access(mocker):
    user = make_user(user_id=2)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, report=rp, is_member=True)
    result = service.get_report(user, 1)
    assert result is rp


def test_get_report_reader_member_has_access(mocker):
    """Reader role is still an active member — can read."""
    user = make_user(user_id=2)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, report=rp, is_member=True, is_contributor=False)
    result = service.get_report(user, 1)
    assert result is rp


def test_get_report_non_member_raises_403(mocker):
    user = make_user(user_id=2)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, report=rp, is_member=False)
    with pytest.raises(ReportAccessDeniedException):
        service.get_report(user, 1)


def test_get_report_no_source_chat_non_creator_raises_403(mocker):
    """Report with no chat: only the creator can access it."""
    user = make_user(user_id=2)
    rp = make_report(report_id=1, created_by=1, source_chat_id=None)
    _patch_access(mocker, report=rp)
    with pytest.raises(ReportAccessDeniedException):
        service.get_report(user, 1)


def test_get_report_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.report_repository.get_by_id", return_value=None)
    with pytest.raises(ReportNotFoundException):
        service.get_report(user, 999)


# ══════════════════════════════════════════════════════════════════════════════
# delete_report — owner or editor only; reader cannot delete
# ══════════════════════════════════════════════════════════════════════════════

def test_delete_creator_can_delete_own_report(mocker):
    user = make_user(user_id=1)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, report=rp)
    soft_delete = mocker.patch(f"{SVC}.report_repository.soft_delete")
    service.delete_report(user, 1)
    soft_delete.assert_called_once_with(rp, deleted_by=1)


def test_delete_contributor_member_can_delete(mocker):
    """Owner or editor role can delete someone else's report."""
    user = make_user(user_id=2)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, report=rp, is_contributor=True)
    soft_delete = mocker.patch(f"{SVC}.report_repository.soft_delete")
    service.delete_report(user, 1)
    soft_delete.assert_called_once()


def test_delete_reader_member_raises_403(mocker):
    """Reader is an active member but NOT a contributor — cannot delete."""
    user = make_user(user_id=2)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, report=rp, is_member=True, is_contributor=False)
    with pytest.raises(ReportAccessDeniedException):
        service.delete_report(user, 1)


def test_delete_non_member_raises_403(mocker):
    user = make_user(user_id=2)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, report=rp, is_member=False, is_contributor=False)
    with pytest.raises(ReportAccessDeniedException):
        service.delete_report(user, 1)


def test_delete_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.report_repository.get_by_id", return_value=None)
    with pytest.raises(ReportNotFoundException):
        service.delete_report(user, 999)


# ══════════════════════════════════════════════════════════════════════════════
# update_report — owner or editor only; reader cannot update
# ══════════════════════════════════════════════════════════════════════════════

def test_update_creator_can_update_own_report(mocker):
    user = make_user(user_id=1)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    updated = make_report(report_id=1, title="Nuevo título")
    _patch_access(mocker, report=rp)
    mocker.patch(f"{SVC}.report_repository.update", return_value=updated)
    result = service.update_report(user, 1, title="Nuevo título")
    assert result.title == "Nuevo título"


def test_update_contributor_member_can_update(mocker):
    """Owner or editor role can update someone else's report."""
    user = make_user(user_id=2)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    updated = make_report(report_id=1, title="Actualizado")
    _patch_access(mocker, report=rp, is_contributor=True)
    mocker.patch(f"{SVC}.report_repository.update", return_value=updated)
    result = service.update_report(user, 1, title="Actualizado")
    assert result.title == "Actualizado"


def test_update_reader_member_raises_403(mocker):
    """Reader is an active member but cannot modify the report."""
    user = make_user(user_id=2)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, report=rp, is_member=True, is_contributor=False)
    with pytest.raises(ReportAccessDeniedException):
        service.update_report(user, 1, title="X")


def test_update_non_member_raises_403(mocker):
    user = make_user(user_id=2)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, report=rp, is_member=False, is_contributor=False)
    with pytest.raises(ReportAccessDeniedException):
        service.update_report(user, 1, title="X")


def test_update_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.report_repository.get_by_id", return_value=None)
    with pytest.raises(ReportNotFoundException):
        service.update_report(user, 999, title="X")


# ══════════════════════════════════════════════════════════════════════════════
# list_reports — chat filter validation
# ══════════════════════════════════════════════════════════════════════════════

def test_list_reports_no_chat_id_returns_user_own(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    repo = mocker.patch(f"{SVC}.report_repository.list_by_user", return_value=[])
    service.list_reports(user, chat_id=None)
    repo.assert_called_once_with(user_id=1, report_type=None)


def test_list_reports_with_chat_id_checks_membership(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=True)
    repo = mocker.patch(f"{SVC}.report_repository.list_by_chat", return_value=[])
    service.list_reports(user, chat_id=5)
    repo.assert_called_once_with(source_chat_id=5, report_type=None)


def test_list_reports_reader_can_list_chat_reports(mocker):
    """Reader role can list reports in a chat (read-only operation)."""
    user = make_user(user_id=2)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=True)
    repo = mocker.patch(f"{SVC}.report_repository.list_by_chat", return_value=[])
    service.list_reports(user, chat_id=5)
    repo.assert_called_once_with(source_chat_id=5, report_type=None)


def test_list_reports_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=None)
    with pytest.raises(ChatNotFoundException):
        service.list_reports(user, chat_id=999)


def test_list_reports_not_chat_member_raises_403(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=False)
    with pytest.raises(ChatAccessDeniedException):
        service.list_reports(user, chat_id=5)


def test_list_reports_with_type_filter(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    repo = mocker.patch(f"{SVC}.report_repository.list_by_user", return_value=[])
    service.list_reports(user, report_type="SITREP", chat_id=None)
    repo.assert_called_once_with(user_id=1, report_type="SITREP")


# ══════════════════════════════════════════════════════════════════════════════
# get_own_report — any active member (used for export)
# ══════════════════════════════════════════════════════════════════════════════

def test_get_own_report_creator_has_access(mocker):
    user = make_user(user_id=1)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, report=rp)
    result = service.get_own_report(user, 1)
    assert result is rp


def test_get_own_report_reader_member_has_access(mocker):
    """Any active member can export (read operation)."""
    user = make_user(user_id=2)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, report=rp, is_member=True)
    result = service.get_own_report(user, 1)
    assert result is rp


def test_get_own_report_non_member_raises_403(mocker):
    user = make_user(user_id=2)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, report=rp, is_member=False)
    with pytest.raises(ReportAccessDeniedException):
        service.get_own_report(user, 1)


def test_get_own_report_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.report_repository.get_by_id", return_value=None)
    with pytest.raises(ReportNotFoundException):
        service.get_own_report(user, 999)


# ══════════════════════════════════════════════════════════════════════════════
# list_all_reports (admin)
# ══════════════════════════════════════════════════════════════════════════════

def test_list_all_reports_passes_type_to_repo(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    repo = mocker.patch(f"{SVC}.report_repository.list_all", return_value=[])
    service.list_all_reports(user, report_type="OPORD")
    repo.assert_called_once_with(report_type="OPORD")


def test_list_all_reports_no_type_passes_none(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    repo = mocker.patch(f"{SVC}.report_repository.list_all", return_value=[])
    service.list_all_reports(user)
    repo.assert_called_once_with(report_type=None)


# ══════════════════════════════════════════════════════════════════════════════
# get_report_admin_export — bypasses access checks (admin only)
# ══════════════════════════════════════════════════════════════════════════════

def test_get_report_admin_export_returns_report_without_access_check(mocker):
    """Admin export bypasses creator/membership checks entirely."""
    user = make_user(user_id=999)  # neither creator nor member
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.report_repository.get_by_id", return_value=rp)
    is_member = mocker.patch(f"{SVC}.membership_repository.is_active_member")
    result = service.get_report_admin_export(user, 1)
    assert result is rp
    is_member.assert_not_called()


def test_get_report_admin_export_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.report_repository.get_by_id", return_value=None)
    with pytest.raises(ReportNotFoundException):
        service.get_report_admin_export(user, 999)


# ══════════════════════════════════════════════════════════════════════════════
# _auto_title helper
# ══════════════════════════════════════════════════════════════════════════════

def test_auto_title_uses_first_line_when_short():
    assert _auto_title("SITREP", "Primera línea\nresto del cuerpo") == "Primera línea"


def test_auto_title_strips_markdown_heading_marks():
    assert _auto_title("SITREP", "#  Título con almohadilla\ncuerpo") == "Título con almohadilla"


def test_auto_title_falls_back_when_first_line_too_long():
    title = _auto_title("INTSUM", "x" * 81)
    assert title.startswith("INTSUM — ")


def test_auto_title_falls_back_when_content_blank():
    title = _auto_title("OPORD", "   \n  ")
    assert title.startswith("OPORD — ")


# ══════════════════════════════════════════════════════════════════════════════
# generate_report (async)
# ══════════════════════════════════════════════════════════════════════════════

def _llm_result(content="Cuerpo del informe", report_type="SITREP", messages=None, fragments=None):
    return ReportGenerateResult(
        report_type=report_type,
        content=content,
        messages=messages if messages is not None else [{"role": "human", "content": "x"}],
        fragments=fragments if fragments is not None else [{"content": "frag", "document": {}}],
    )


@pytest.mark.asyncio
async def test_generate_report_without_chat_creates_and_returns(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    result = _llm_result()
    mocker.patch(f"{SVC}.llm_client.generate_report", new_callable=AsyncMock, return_value=result)
    created = make_report(report_id=5)
    create = mocker.patch(f"{SVC}.report_repository.create", return_value=created)
    report, messages, fragments = await service.generate_report(user, "SITREP", "Genera", "direct")
    assert report is created
    assert messages == result.messages
    assert fragments == result.fragments
    _, kwargs = create.call_args
    assert kwargs["source_chat_id"] is None
    assert kwargs["user_id"] == 1


@pytest.mark.asyncio
async def test_generate_report_no_chat_does_not_query_history(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.report_repository.create", return_value=make_report())
    recent = mocker.patch(f"{SVC}.message_repository.get_recent_messages")
    llm = mocker.patch(f"{SVC}.llm_client.generate_report", new_callable=AsyncMock, return_value=_llm_result())
    await service.generate_report(user, "SITREP", "Genera", "direct")
    recent.assert_not_called()
    _, kwargs = llm.call_args
    assert kwargs["messages"] == [{"role": "human", "content": "Genera"}]


@pytest.mark.asyncio
async def test_generate_report_with_chat_builds_history_with_role_mapping(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{SVC}.membership_repository.is_active_contributor", return_value=True)
    msgs = [
        make_message(msg_id=1, sender_type="user", message="pregunta"),
        make_message(msg_id=2, sender_type="system", message="respuesta"),
    ]
    mocker.patch(f"{SVC}.message_repository.get_recent_messages", return_value=msgs)
    llm = mocker.patch(f"{SVC}.llm_client.generate_report", new_callable=AsyncMock, return_value=_llm_result())
    mocker.patch(f"{SVC}.report_repository.create", return_value=make_report())
    await service.generate_report(user, "SITREP", "Genera", "direct", chat_id=10)
    _, kwargs = llm.call_args
    history = kwargs["messages"]
    roles = {h["content"]: h["role"] for h in history}
    assert roles["pregunta"] == "human"   # USER → human
    assert roles["respuesta"] == "assistant"  # SYSTEM → assistant
    assert history[-1] == {"role": "human", "content": "Genera"}


@pytest.mark.asyncio
async def test_generate_report_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=None)
    with pytest.raises(ChatNotFoundException):
        await service.generate_report(user, "SITREP", "x", "direct", chat_id=99)


@pytest.mark.asyncio
async def test_generate_report_non_contributor_raises_403(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{SVC}.membership_repository.is_active_contributor", return_value=False)
    with pytest.raises(ChatAccessDeniedException):
        await service.generate_report(user, "SITREP", "x", "direct", chat_id=10)


@pytest.mark.asyncio
async def test_generate_report_llm_http_error_raises_502(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(
        f"{SVC}.llm_client.generate_report",
        new_callable=AsyncMock,
        side_effect=HttpClientException("boom", status_code=503),
    )
    with pytest.raises(LLMServiceException):
        await service.generate_report(user, "SITREP", "x", "direct")


@pytest.mark.asyncio
async def test_generate_report_empty_content_raises_and_skips_create(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(
        f"{SVC}.llm_client.generate_report",
        new_callable=AsyncMock,
        return_value=_llm_result(content="   "),
    )
    create = mocker.patch(f"{SVC}.report_repository.create")
    with pytest.raises(LLMServiceException):
        await service.generate_report(user, "SITREP", "x", "direct")
    create.assert_not_called()


@pytest.mark.asyncio
async def test_generate_report_uses_result_type_and_auto_title(mocker):
    """The persisted report uses the LLM's returned type and an auto title from content."""
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(
        f"{SVC}.llm_client.generate_report",
        new_callable=AsyncMock,
        return_value=_llm_result(content="Resumen ejecutivo\ndetalle", report_type="INTSUM"),
    )
    create = mocker.patch(f"{SVC}.report_repository.create", return_value=make_report())
    await service.generate_report(user, "SITREP", "x", "direct")
    _, kwargs = create.call_args
    assert kwargs["type"] == "INTSUM"            # result.report_type, not the requested type
    assert kwargs["title"] == "Resumen ejecutivo"  # derived by _auto_title
