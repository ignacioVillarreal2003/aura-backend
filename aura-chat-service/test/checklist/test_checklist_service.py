import pytest

from apps.checklist.exceptions import ChecklistAccessDeniedException, ChecklistNotFoundException
from apps.checklist.services.checklist_service import ChecklistService, _items_to_sections
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from core.exceptions.base import InsufficientPermissionsException
from test.conftest import make_checklist, make_user

SVC = "apps.checklist.services.checklist_service"


# ══════════════════════════════════════════════════════════════════════════════
# _items_to_sections
# ══════════════════════════════════════════════════════════════════════════════

def test_items_to_sections_groups_items_by_section():
    items = [
        {"section": "Alpha", "text": "Paso 1", "is_checked": False, "notes": "", "order": 0},
        {"section": "Beta",  "text": "Paso 2", "is_checked": False, "notes": "", "order": 0},
        {"section": "Alpha", "text": "Paso 3", "is_checked": False, "notes": "", "order": 1},
    ]
    sections = _items_to_sections(items)
    assert len(sections) == 2
    alpha = next(s for s in sections if s["title"] == "Alpha")
    assert len(alpha["items"]) == 2


def test_items_to_sections_preserves_first_appearance_order():
    items = [
        {"section": "B", "text": "x", "is_checked": False, "notes": "", "order": 0},
        {"section": "A", "text": "y", "is_checked": False, "notes": "", "order": 0},
        {"section": "C", "text": "z", "is_checked": False, "notes": "", "order": 0},
    ]
    sections = _items_to_sections(items)
    assert [s["title"] for s in sections] == ["B", "A", "C"]


def test_items_to_sections_sorts_items_by_order_within_section():
    items = [
        {"section": "X", "text": "tercero", "is_checked": False, "notes": "", "order": 2},
        {"section": "X", "text": "primero", "is_checked": False, "notes": "", "order": 0},
        {"section": "X", "text": "segundo", "is_checked": False, "notes": "", "order": 1},
    ]
    sections = _items_to_sections(items)
    texts = [it["text"] for it in sections[0]["items"]]
    assert texts == ["primero", "segundo", "tercero"]


def test_items_to_sections_missing_section_defaults_to_general():
    items = [{"text": "sin sección", "is_checked": False, "notes": "", "order": 0}]
    sections = _items_to_sections(items)
    assert len(sections) == 1
    assert sections[0]["title"] == "General"


def test_items_to_sections_missing_order_defaults_to_zero():
    items = [
        {"section": "S", "text": "a", "is_checked": False, "notes": ""},
        {"section": "S", "text": "b", "is_checked": False, "notes": ""},
    ]
    sections = _items_to_sections(items)
    # Both order=0 → both present, no crash
    assert len(sections[0]["items"]) == 2


def test_items_to_sections_assigns_zero_indexed_section_positions():
    items = [
        {"section": "A", "text": "x", "is_checked": False, "notes": "", "order": 0},
        {"section": "B", "text": "y", "is_checked": False, "notes": "", "order": 0},
        {"section": "C", "text": "z", "is_checked": False, "notes": "", "order": 0},
    ]
    sections = _items_to_sections(items)
    assert [s["position"] for s in sections] == [0, 1, 2]


def test_items_to_sections_assigns_zero_indexed_item_positions():
    items = [
        {"section": "S", "text": "a", "is_checked": False, "notes": "", "order": 0},
        {"section": "S", "text": "b", "is_checked": False, "notes": "", "order": 1},
        {"section": "S", "text": "c", "is_checked": False, "notes": "", "order": 2},
    ]
    sections = _items_to_sections(items)
    assert [it["position"] for it in sections[0]["items"]] == [0, 1, 2]


def test_items_to_sections_preserves_is_checked_and_notes():
    items = [{"section": "S", "text": "item", "is_checked": True, "notes": "nota importante", "order": 0}]
    sections = _items_to_sections(items)
    item = sections[0]["items"][0]
    assert item["is_checked"] is True
    assert item["notes"] == "nota importante"


def test_items_to_sections_empty_list_returns_empty():
    assert _items_to_sections([]) == []


def test_items_to_sections_single_item_creates_one_section_one_item():
    items = [{"section": "Solo", "text": "único", "is_checked": False, "notes": "", "order": 0}]
    sections = _items_to_sections(items)
    assert len(sections) == 1
    assert len(sections[0]["items"]) == 1
    assert sections[0]["items"][0]["text"] == "único"


# ══════════════════════════════════════════════════════════════════════════════
# Access control — get_checklist / get_own_checklist
# ══════════════════════════════════════════════════════════════════════════════

service = ChecklistService()


def _patch_access(mocker, *, checklist, is_member=False, is_contributor=False):
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.checklist_repository.get_by_id", return_value=checklist)
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=is_member)
    mocker.patch(f"{SVC}.membership_repository.is_active_contributor", return_value=is_contributor)


def test_get_checklist_creator_always_has_access(mocker):
    user = make_user(user_id=1)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, checklist=cl)
    result = service.get_checklist(user, 1)
    assert result is cl


def test_get_checklist_active_member_has_access(mocker):
    user = make_user(user_id=2)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, checklist=cl, is_member=True)
    result = service.get_checklist(user, 1)
    assert result is cl


def test_get_checklist_non_member_raises_403(mocker):
    user = make_user(user_id=2)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, checklist=cl, is_member=False)
    with pytest.raises(ChecklistAccessDeniedException):
        service.get_checklist(user, 1)


def test_get_checklist_no_source_chat_non_creator_raises_403(mocker):
    user = make_user(user_id=2)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=None)
    _patch_access(mocker, checklist=cl)
    with pytest.raises(ChecklistAccessDeniedException):
        service.get_checklist(user, 1)


def test_get_checklist_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.checklist_repository.get_by_id", return_value=None)
    with pytest.raises(ChecklistNotFoundException):
        service.get_checklist(user, 999)


# ══════════════════════════════════════════════════════════════════════════════
# Access control — delete_checklist (owner or editor; reader cannot delete)
# ══════════════════════════════════════════════════════════════════════════════

def test_delete_creator_can_delete_own_checklist(mocker):
    user = make_user(user_id=1)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, checklist=cl)
    soft_delete = mocker.patch(f"{SVC}.checklist_repository.soft_delete")
    service.delete_checklist(user, 1)
    soft_delete.assert_called_once_with(cl, deleted_by=1)


def test_delete_contributor_member_can_delete(mocker):
    """Owner or editor role can delete someone else's checklist."""
    user = make_user(user_id=2)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, checklist=cl, is_contributor=True)
    soft_delete = mocker.patch(f"{SVC}.checklist_repository.soft_delete")
    service.delete_checklist(user, 1)
    soft_delete.assert_called_once()


def test_delete_reader_member_raises_403(mocker):
    """Reader role is active member but NOT a contributor — cannot delete."""
    user = make_user(user_id=2)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, checklist=cl, is_member=True, is_contributor=False)
    with pytest.raises(ChecklistAccessDeniedException):
        service.delete_checklist(user, 1)


def test_delete_non_member_raises_403(mocker):
    user = make_user(user_id=2)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, checklist=cl, is_member=False, is_contributor=False)
    with pytest.raises(ChecklistAccessDeniedException):
        service.delete_checklist(user, 1)


def test_delete_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.checklist_repository.get_by_id", return_value=None)
    with pytest.raises(ChecklistNotFoundException):
        service.delete_checklist(user, 999)


# ══════════════════════════════════════════════════════════════════════════════
# Access control — update_checklist (owner or editor; reader cannot update)
# ══════════════════════════════════════════════════════════════════════════════

def test_update_contributor_member_can_update(mocker):
    user = make_user(user_id=2)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    updated = make_checklist(cl_id=1, title="Nuevo")
    _patch_access(mocker, checklist=cl, is_contributor=True)
    mocker.patch(f"{SVC}.checklist_repository.update", return_value=updated)
    result = service.update_checklist(user, 1, title="Nuevo")
    assert result.title == "Nuevo"


def test_update_reader_member_raises_403(mocker):
    """Reader is an active member but cannot modify the checklist."""
    user = make_user(user_id=2)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, checklist=cl, is_member=True, is_contributor=False)
    with pytest.raises(ChecklistAccessDeniedException):
        service.update_checklist(user, 1, title="X")


def test_update_non_member_raises_403(mocker):
    user = make_user(user_id=2)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, checklist=cl, is_member=False, is_contributor=False)
    with pytest.raises(ChecklistAccessDeniedException):
        service.update_checklist(user, 1, title="X")


# ══════════════════════════════════════════════════════════════════════════════
# list_checklists — chat filter validation
# ══════════════════════════════════════════════════════════════════════════════

def test_list_checklists_no_chat_id_returns_user_own(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    repo = mocker.patch(f"{SVC}.checklist_repository.list_by_user", return_value=[])
    service.list_checklists(user, chat_id=None)
    repo.assert_called_once_with(user_id=1)


def test_list_checklists_with_chat_id_checks_membership(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=True)
    repo = mocker.patch(f"{SVC}.checklist_repository.list_by_chat", return_value=[])
    service.list_checklists(user, chat_id=5)
    repo.assert_called_once_with(source_chat_id=5)


def test_list_checklists_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=None)
    with pytest.raises(ChatNotFoundException):
        service.list_checklists(user, chat_id=999)


def test_list_checklists_not_chat_member_raises_403(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=False)
    with pytest.raises(ChatAccessDeniedException):
        service.list_checklists(user, chat_id=5)
