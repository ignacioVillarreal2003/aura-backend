import pytest

from apps.report.exceptions import ReportAccessDeniedException, ReportNotFoundException
from apps.report.services.report_service import ReportService
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from test.conftest import make_report, make_user

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
