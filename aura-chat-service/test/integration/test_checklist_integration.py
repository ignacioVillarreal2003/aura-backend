import pytest

from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.checklist.exceptions import ChecklistAccessDeniedException, ChecklistNotFoundException
from apps.checklist.models import Checklist, ChecklistItem, ChecklistSection
from apps.checklist.repositories.checklist_repository import checklist_repository
from apps.checklist.services.checklist_service import checklist_service

pytestmark = pytest.mark.django_db


def _default_sections():
    return [
        {
            "title": "Fase 1",
            "position": 0,
            "items": [
                {"text": "Paso 1", "is_checked": False, "notes": "", "position": 0},
                {"text": "Paso 2", "is_checked": True, "notes": "ok", "position": 1},
            ],
        },
    ]


def _make_checklist(creator, sections=None, **overrides):
    params = dict(
        user_id=creator.id,
        title="Checklist",
        sections=sections if sections is not None else _default_sections(),
        mode=Checklist.Mode.DIRECT,
        source_chat_id=None,
    )
    params.update(overrides)
    return checklist_repository.create(**params)


# ---------------------------------------------------------------------------
# create — checklist + sections + items persistence
# ---------------------------------------------------------------------------

def test_create_persists_checklist_sections_and_items(owner):
    checklist = _make_checklist(owner, title="Persistida")
    assert Checklist.objects.filter(id=checklist.id, title="Persistida").exists()
    section = ChecklistSection.objects.get(checklist_id=checklist.id)
    assert section.title == "Fase 1"
    assert ChecklistItem.objects.filter(section_id=section.id).count() == 2


def test_create_sets_created_by(owner):
    checklist = _make_checklist(owner)
    assert checklist.created_by == owner.id


def test_create_returns_prefetched_sections_and_items(owner):
    checklist = _make_checklist(owner)
    sections = list(checklist.sections.all())
    assert len(sections) == 1
    assert len(list(sections[0].items.all())) == 2


# ---------------------------------------------------------------------------
# get_checklist — access control with real memberships
# ---------------------------------------------------------------------------

def test_get_checklist_creator_has_access(owner):
    checklist = _make_checklist(owner)
    assert checklist_service.get_checklist(owner, checklist.id).id == checklist.id


def test_get_checklist_not_found_raises(owner):
    with pytest.raises(ChecklistNotFoundException):
        checklist_service.get_checklist(owner, 999999)


def test_get_checklist_no_chat_non_creator_denied(owner, other_user):
    checklist = _make_checklist(owner, source_chat_id=None)
    with pytest.raises(ChecklistAccessDeniedException):
        checklist_service.get_checklist(other_user, checklist.id)


def test_get_checklist_chat_member_has_access(chat_with_member, owner, member_user):
    checklist = _make_checklist(owner, source_chat_id=chat_with_member.id)
    assert checklist_service.get_checklist(member_user, checklist.id).id == checklist.id


def test_get_checklist_non_member_of_chat_denied(chat, owner, other_user):
    checklist = _make_checklist(owner, source_chat_id=chat.id)
    with pytest.raises(ChecklistAccessDeniedException):
        checklist_service.get_checklist(other_user, checklist.id)


# ---------------------------------------------------------------------------
# list_checklists / list_all_checklists — incl. count annotations
# ---------------------------------------------------------------------------

def test_list_checklists_returns_own_with_counts(owner):
    checklist = _make_checklist(owner)  # 2 items, 1 checked
    by_id = {c.id: c for c in checklist_service.list_checklists(owner)}
    assert checklist.id in by_id
    assert by_id[checklist.id].item_count == 2
    assert by_id[checklist.id].checked_count == 1


def test_list_checklists_excludes_other_users(owner, other_user):
    mine = _make_checklist(owner)
    theirs = _make_checklist(other_user)
    ids = [c.id for c in checklist_service.list_checklists(owner)]
    assert mine.id in ids
    assert theirs.id not in ids


def test_list_checklists_by_chat_returns_all_members(chat_with_member, owner, member_user):
    c_owner = _make_checklist(owner, source_chat_id=chat_with_member.id)
    c_member = _make_checklist(member_user, source_chat_id=chat_with_member.id)
    ids = [c.id for c in checklist_service.list_checklists(member_user, chat_id=chat_with_member.id)]
    assert c_owner.id in ids
    assert c_member.id in ids


def test_list_checklists_chat_not_found_raises(owner):
    with pytest.raises(ChatNotFoundException):
        checklist_service.list_checklists(owner, chat_id=999999)


def test_list_checklists_chat_non_member_raises(chat, other_user):
    with pytest.raises(ChatAccessDeniedException):
        checklist_service.list_checklists(other_user, chat_id=chat.id)


def test_list_all_checklists_includes_other_users(owner, other_user):
    mine = _make_checklist(owner)
    theirs = _make_checklist(other_user)
    ids = [c.id for c in checklist_service.list_all_checklists(owner)]
    assert mine.id in ids
    assert theirs.id in ids


# ---------------------------------------------------------------------------
# update_checklist — exercises the repository's replace-sections logic
# ---------------------------------------------------------------------------

def test_update_title_persists(owner):
    checklist = _make_checklist(owner, title="Viejo")
    checklist_service.update_checklist(owner, checklist.id, title="Nuevo")
    checklist.refresh_from_db()
    assert checklist.title == "Nuevo"
    assert checklist.updated_by == owner.id


def test_update_sections_replaces_old_sections_and_items(owner):
    checklist = _make_checklist(owner)  # 1 section / 2 items
    new_sections = [
        {
            "title": "Nueva Fase",
            "position": 0,
            "items": [{"text": "Único", "is_checked": False, "notes": "", "position": 0}],
        },
    ]
    checklist_service.update_checklist(owner, checklist.id, sections=new_sections)
    titles = list(
        ChecklistSection.objects.filter(checklist_id=checklist.id).values_list("title", flat=True)
    )
    assert titles == ["Nueva Fase"]
    section = ChecklistSection.objects.get(checklist_id=checklist.id)
    item_texts = list(
        ChecklistItem.objects.filter(section_id=section.id).values_list("text", flat=True)
    )
    assert item_texts == ["Único"]


def test_update_sections_only_sets_updated_by(owner):
    checklist = _make_checklist(owner)
    new_sections = [{"title": "X", "position": 0, "items": []}]
    checklist_service.update_checklist(owner, checklist.id, sections=new_sections)
    checklist.refresh_from_db()
    assert checklist.updated_by == owner.id


def test_update_no_fields_is_noop(owner):
    checklist = _make_checklist(owner, title="Intacta")
    checklist_service.update_checklist(owner, checklist.id)
    checklist.refresh_from_db()
    assert checklist.title == "Intacta"
    assert checklist.updated_by is None


def test_update_chat_editor_can_update(chat_with_member, owner, member_user):
    checklist = _make_checklist(owner, source_chat_id=chat_with_member.id)
    checklist_service.update_checklist(member_user, checklist.id, title="Editado por miembro")
    checklist.refresh_from_db()
    assert checklist.title == "Editado por miembro"


def test_update_non_member_denied(owner, other_user):
    checklist = _make_checklist(owner, source_chat_id=None)
    with pytest.raises(ChecklistAccessDeniedException):
        checklist_service.update_checklist(other_user, checklist.id, title="Hack")


# ---------------------------------------------------------------------------
# delete_checklist — soft delete
# ---------------------------------------------------------------------------

def test_delete_soft_deletes(owner):
    checklist = _make_checklist(owner)
    checklist_id = checklist.id
    checklist_service.delete_checklist(owner, checklist_id)
    assert not Checklist.objects.filter(id=checklist_id).exists()
    assert Checklist.objects.all_with_deleted().filter(
        id=checklist_id, deleted_at__isnull=False
    ).exists()


def test_delete_sets_deleted_by(owner):
    checklist = _make_checklist(owner)
    checklist_id = checklist.id
    checklist_service.delete_checklist(owner, checklist_id)
    deleted = Checklist.objects.all_with_deleted().get(id=checklist_id)
    assert deleted.deleted_by == owner.id


def test_delete_chat_editor_can_delete(chat_with_member, owner, member_user):
    checklist = _make_checklist(owner, source_chat_id=chat_with_member.id)
    checklist_id = checklist.id
    checklist_service.delete_checklist(member_user, checklist_id)
    assert not Checklist.objects.filter(id=checklist_id).exists()


def test_delete_non_member_denied(owner, other_user):
    checklist = _make_checklist(owner, source_chat_id=None)
    with pytest.raises(ChecklistAccessDeniedException):
        checklist_service.delete_checklist(other_user, checklist.id)
