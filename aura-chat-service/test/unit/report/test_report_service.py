from unittest.mock import AsyncMock

import pytest

from apps.artifact_report.exceptions import (
    LLMServiceException,
    ReportAccessDeniedException,
    ReportNotFoundException,
)
from apps.artifact_report.services.report_service import ReportService, _derive_title_and_description
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import ReportGenerateResult
from test.conftest import make_message, make_report, make_user

SVC = "apps.artifact_report.services.report_service"
# get/list/delete now delegate to ArtifactCrudService; access checks live in the
# shared base + artifact_access, so patch permissions/membership there.
ACCESS = "apps.artifact.services.artifact_access"
CRUD = "apps.artifact.services.artifact_crud_service"

service = ReportService()


@pytest.fixture(autouse=True)
def _patch_atomic(mocker):
    """delete/generate wrap writes in transaction.atomic(); no-op it for mock-only tests."""
    mocker.patch("django.db.transaction.Atomic.__enter__", return_value=None)
    mocker.patch("django.db.transaction.Atomic.__exit__", return_value=False)


def _patch_delete_extras(mocker):
    """The shared _delete also cleans up interactions and soft-deletes the artifact."""
    mocker.patch(f"{CRUD}._cleanup_artifact_interactions")
    mocker.patch(f"{CRUD}.artifact_repository.soft_delete")


def _patch_access(mocker, *, report, is_member=False, is_contributor=False):
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.report_repository.get_by_id", return_value=report)
    mocker.patch(f"{SVC}.report_repository.get_by_id_for_update", return_value=report)
    mocker.patch(f"{ACCESS}.membership_repository.is_active_member", return_value=is_member)
    mocker.patch(f"{ACCESS}.membership_repository.is_active_contributor", return_value=is_contributor)


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
    _patch_delete_extras(mocker)
    soft_delete = mocker.patch(f"{SVC}.report_repository.soft_delete")
    service.delete_report(user, 1)
    soft_delete.assert_called_once_with(rp, deleted_by=1)


def test_delete_contributor_member_can_delete(mocker):
    """Owner or editor role can delete someone else's report."""
    user = make_user(user_id=2)
    rp = make_report(report_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, report=rp, is_contributor=True)
    _patch_delete_extras(mocker)
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
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.report_repository.get_by_id_for_update", return_value=None)
    with pytest.raises(ReportNotFoundException):
        service.delete_report(user, 999)


# ══════════════════════════════════════════════════════════════════════════════
# list_reports — chat filter validation (always scoped to a chat)
# ══════════════════════════════════════════════════════════════════════════════

def test_list_reports_with_chat_id_checks_membership(mocker):
    user = make_user(user_id=1)
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{CRUD}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{CRUD}.membership_repository.is_active_member", return_value=True)
    repo = mocker.patch(f"{SVC}.report_repository.list_by_chat", return_value=[])
    service.list_reports(user, chat_id=5)
    repo.assert_called_once_with(source_chat_id=5, report_type=None)


def test_list_reports_reader_can_list_chat_reports(mocker):
    """Reader role can list reports in a chat (read-only operation)."""
    user = make_user(user_id=2)
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{CRUD}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{CRUD}.membership_repository.is_active_member", return_value=True)
    repo = mocker.patch(f"{SVC}.report_repository.list_by_chat", return_value=[])
    service.list_reports(user, chat_id=5)
    repo.assert_called_once_with(source_chat_id=5, report_type=None)


def test_list_reports_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{CRUD}.chat_repository.get_by_id", return_value=None)
    with pytest.raises(ChatNotFoundException):
        service.list_reports(user, chat_id=999)


def test_list_reports_not_chat_member_raises_403(mocker):
    user = make_user(user_id=1)
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{CRUD}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{CRUD}.membership_repository.is_active_member", return_value=False)
    with pytest.raises(ChatAccessDeniedException):
        service.list_reports(user, chat_id=5)


def test_list_reports_with_type_filter(mocker):
    user = make_user(user_id=1)
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{CRUD}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{CRUD}.membership_repository.is_active_member", return_value=True)
    repo = mocker.patch(f"{SVC}.report_repository.list_by_chat", return_value=[])
    service.list_reports(user, report_type="SITREP", chat_id=5)
    repo.assert_called_once_with(source_chat_id=5, report_type="SITREP")


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
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.report_repository.get_by_id", return_value=rp)
    is_member = mocker.patch(f"{ACCESS}.membership_repository.is_active_member")
    result = service.get_report_admin_export(user, 1)
    assert result is rp
    is_member.assert_not_called()


def test_get_report_admin_export_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.report_repository.get_by_id", return_value=None)
    with pytest.raises(ReportNotFoundException):
        service.get_report_admin_export(user, 999)


# ══════════════════════════════════════════════════════════════════════════════
# _derive_title_and_description helper
# ══════════════════════════════════════════════════════════════════════════════

_SITREP_SAMPLE = """CLASIFICACIÓN: RESERVADO

SITREP NR: 014
DTG: 211430Z JUN 26
UNIDAD: Escuadrón Aéreo Nº 2

1. SITUACIÓN
   a. Fuerzas propias: Patrulla en zona norte.

2. MISIÓN
   El Escuadrón Aéreo Nº 2 asegura el espacio aéreo fronterizo durante 72 horas.

3. EJECUCIÓN
   a. Concepto: vuelos de reconocimiento.
"""


def test_derive_title_uses_mission_first_sentence():
    title, description = _derive_title_and_description("SITREP", _SITREP_SAMPLE)
    assert title.startswith("El Escuadrón Aéreo Nº 2 asegura el espacio aéreo")
    assert "CLASIFICACIÓN" not in title
    assert description.startswith("El Escuadrón Aéreo Nº 2 asegura")


def test_derive_title_ignores_classification_header():
    # La línea de clasificación nunca debe convertirse en el título (bug original).
    title, _ = _derive_title_and_description("SITREP", _SITREP_SAMPLE)
    assert not title.upper().startswith("CLASIFICACIÓN")


def test_derive_title_falls_back_to_unidad_when_no_mission():
    content = "CLASIFICACIÓN: RESERVADO\n\nINTSUM NR: 003\nUNIDAD: Base Aérea Sur\n"
    title, description = _derive_title_and_description("INTSUM", content)
    assert title == "Base Aérea Sur"
    assert description == ""


def test_derive_title_falls_back_to_type_and_date_when_blank():
    title, description = _derive_title_and_description("OPORD", "   \n  ")
    assert title.startswith("Informe OPORD — ")
    assert description == ""


def test_derive_title_truncates_long_mission():
    content = "2. MISIÓN\n   " + ("palabra " * 40)
    title, description = _derive_title_and_description("SITREP", content)
    assert len(title) <= 80
    assert len(description) <= 240


# ══════════════════════════════════════════════════════════════════════════════
# generate_report (async)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_generate_report_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=None)
    with pytest.raises(ChatNotFoundException):
        await service.generate_report(user, "SITREP", "x", chat_id=99)
