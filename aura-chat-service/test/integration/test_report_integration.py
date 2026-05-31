import pytest

from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.report.exceptions import ReportAccessDeniedException, ReportNotFoundException
from apps.report.models import Report
from apps.report.repositories.report_repository import report_repository
from apps.report.services.report_service import report_service

pytestmark = pytest.mark.django_db


def _make_report(creator, **overrides):
    params = dict(
        user_id=creator.id,
        type=Report.Type.SITREP,
        title="Informe",
        content="Contenido del informe",
        mode=Report.Mode.DIRECT,
        source_chat_id=None,
    )
    params.update(overrides)
    return report_repository.create(**params)


# ---------------------------------------------------------------------------
# create / persistence
# ---------------------------------------------------------------------------

def test_create_report_persists_to_db(owner):
    report = _make_report(owner, title="Persistido")
    assert Report.objects.filter(id=report.id, title="Persistido").exists()


def test_create_report_sets_created_by(owner):
    report = _make_report(owner)
    assert report.created_by == owner.id


# ---------------------------------------------------------------------------
# get_report — access control with real memberships
# ---------------------------------------------------------------------------

def test_get_report_creator_has_access(owner):
    report = _make_report(owner)
    assert report_service.get_report(owner, report.id).id == report.id


def test_get_report_not_found_raises(owner):
    with pytest.raises(ReportNotFoundException):
        report_service.get_report(owner, 999999)


def test_get_report_no_chat_non_creator_denied(owner, other_user):
    report = _make_report(owner, source_chat_id=None)
    with pytest.raises(ReportAccessDeniedException):
        report_service.get_report(other_user, report.id)


def test_get_report_chat_member_has_access(chat_with_member, owner, member_user):
    report = _make_report(owner, source_chat_id=chat_with_member.id)
    assert report_service.get_report(member_user, report.id).id == report.id


def test_get_report_non_member_of_chat_denied(chat, owner, other_user):
    report = _make_report(owner, source_chat_id=chat.id)
    with pytest.raises(ReportAccessDeniedException):
        report_service.get_report(other_user, report.id)


# ---------------------------------------------------------------------------
# list_reports / list_all_reports
# ---------------------------------------------------------------------------

def test_list_reports_returns_own(owner):
    r1 = _make_report(owner, title="A")
    r2 = _make_report(owner, title="B")
    ids = [r.id for r in report_service.list_reports(owner)]
    assert r1.id in ids
    assert r2.id in ids


def test_list_reports_excludes_other_users(owner, other_user):
    mine = _make_report(owner)
    theirs = _make_report(other_user)
    ids = [r.id for r in report_service.list_reports(owner)]
    assert mine.id in ids
    assert theirs.id not in ids


def test_list_reports_filters_by_type(owner):
    sitrep = _make_report(owner, type=Report.Type.SITREP)
    opord = _make_report(owner, type=Report.Type.OPORD)
    ids = [r.id for r in report_service.list_reports(owner, report_type=Report.Type.SITREP)]
    assert sitrep.id in ids
    assert opord.id not in ids


def test_list_reports_by_chat_returns_all_members_reports(chat_with_member, owner, member_user):
    r_owner = _make_report(owner, source_chat_id=chat_with_member.id)
    r_member = _make_report(member_user, source_chat_id=chat_with_member.id)
    ids = [r.id for r in report_service.list_reports(member_user, chat_id=chat_with_member.id)]
    assert r_owner.id in ids   # a member sees reports created by others in the chat
    assert r_member.id in ids


def test_list_reports_chat_not_found_raises(owner):
    with pytest.raises(ChatNotFoundException):
        report_service.list_reports(owner, chat_id=999999)


def test_list_reports_chat_non_member_raises(chat, other_user):
    with pytest.raises(ChatAccessDeniedException):
        report_service.list_reports(other_user, chat_id=chat.id)


def test_list_all_reports_includes_other_users(owner, other_user):
    mine = _make_report(owner)
    theirs = _make_report(other_user)
    ids = [r.id for r in report_service.list_all_reports(owner)]
    assert mine.id in ids
    assert theirs.id in ids


# ---------------------------------------------------------------------------
# update_report — exercises the repository's field-by-field update logic
# ---------------------------------------------------------------------------

def test_update_report_persists_title(owner):
    report = _make_report(owner, title="Viejo")
    report_service.update_report(owner, report.id, title="Nuevo")
    report.refresh_from_db()
    assert report.title == "Nuevo"


def test_update_report_sets_updated_by(owner):
    report = _make_report(owner)
    report_service.update_report(owner, report.id, content="Otro contenido")
    report.refresh_from_db()
    assert report.updated_by == owner.id


def test_update_report_partial_only_changes_provided_field(owner):
    report = _make_report(owner, title="Titulo", content="Contenido")
    report_service.update_report(owner, report.id, content="Nuevo contenido")
    report.refresh_from_db()
    assert report.content == "Nuevo contenido"
    assert report.title == "Titulo"  # untouched


def test_update_report_no_fields_is_noop(owner):
    """Both fields None → repository performs no write and leaves updated_by unset."""
    report = _make_report(owner, title="Intacto")
    report_service.update_report(owner, report.id)
    report.refresh_from_db()
    assert report.title == "Intacto"
    assert report.updated_by is None


def test_update_report_chat_editor_can_update(chat_with_member, owner, member_user):
    report = _make_report(owner, source_chat_id=chat_with_member.id)
    report_service.update_report(member_user, report.id, title="Editado por miembro")
    report.refresh_from_db()
    assert report.title == "Editado por miembro"


def test_update_report_non_member_denied(owner, other_user):
    report = _make_report(owner, source_chat_id=None)
    with pytest.raises(ReportAccessDeniedException):
        report_service.update_report(other_user, report.id, title="Hack")


# ---------------------------------------------------------------------------
# delete_report — soft delete
# ---------------------------------------------------------------------------

def test_delete_report_soft_deletes(owner):
    report = _make_report(owner)
    report_id = report.id
    report_service.delete_report(owner, report_id)
    assert not Report.objects.filter(id=report_id).exists()
    assert Report.objects.all_with_deleted().filter(
        id=report_id, deleted_at__isnull=False
    ).exists()


def test_delete_report_sets_deleted_by(owner):
    report = _make_report(owner)
    report_id = report.id
    report_service.delete_report(owner, report_id)
    deleted = Report.objects.all_with_deleted().get(id=report_id)
    assert deleted.deleted_by == owner.id


def test_delete_report_chat_editor_can_delete(chat_with_member, owner, member_user):
    report = _make_report(owner, source_chat_id=chat_with_member.id)
    report_id = report.id
    report_service.delete_report(member_user, report_id)
    assert not Report.objects.filter(id=report_id).exists()


def test_delete_report_non_member_denied(owner, other_user):
    report = _make_report(owner, source_chat_id=None)
    with pytest.raises(ReportAccessDeniedException):
        report_service.delete_report(other_user, report.id)
