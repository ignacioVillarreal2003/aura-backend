from unittest.mock import AsyncMock

import pytest

from apps.artifact_checklist.exceptions import (
    ChecklistAccessDeniedException,
    ChecklistNotFoundException,
    LLMServiceException,
)
from apps.artifact_checklist.services.checklist_service import ChecklistService, _items_to_sections
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import ChecklistGenerateResult
from core.exceptions.base import InsufficientPermissionsException
from test.conftest import make_checklist, make_message, make_user

SVC = "apps.artifact_checklist.services.checklist_service"


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

# get/list/delete delegate to ArtifactCrudService; access lives in the shared base.
ACCESS = "apps.artifact.services.artifact_access"
CRUD = "apps.artifact.services.artifact_crud_service"


@pytest.fixture(autouse=True)
def _patch_atomic(mocker):
    mocker.patch("django.db.transaction.Atomic.__enter__", return_value=None)
    mocker.patch("django.db.transaction.Atomic.__exit__", return_value=False)


def _patch_delete_extras(mocker):
    mocker.patch(f"{CRUD}._cleanup_artifact_interactions")
    mocker.patch(f"{CRUD}.artifact_repository.soft_delete")


def _patch_access(mocker, *, checklist, is_member=False, is_contributor=False):
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.checklist_repository.get_by_id", return_value=checklist)
    mocker.patch(f"{SVC}.checklist_repository.get_by_id_for_update", return_value=checklist)
    mocker.patch(f"{ACCESS}.membership_repository.is_active_member", return_value=is_member)
    mocker.patch(f"{ACCESS}.membership_repository.is_active_contributor", return_value=is_contributor)


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
    _patch_delete_extras(mocker)
    soft_delete = mocker.patch(f"{SVC}.checklist_repository.soft_delete")
    service.delete_checklist(user, 1)
    soft_delete.assert_called_once_with(cl, deleted_by=1)


def test_delete_contributor_member_can_delete(mocker):
    """Owner or editor role can delete someone else's checklist."""
    user = make_user(user_id=2)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, checklist=cl, is_contributor=True)
    _patch_delete_extras(mocker)
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
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.checklist_repository.get_by_id_for_update", return_value=None)
    with pytest.raises(ChecklistNotFoundException):
        service.delete_checklist(user, 999)


# ══════════════════════════════════════════════════════════════════════════════
# list_checklists — chat filter validation (always scoped to a chat)
# ══════════════════════════════════════════════════════════════════════════════

def test_list_checklists_with_chat_id_checks_membership(mocker):
    user = make_user(user_id=1)
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{CRUD}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{CRUD}.membership_repository.is_active_member", return_value=True)
    repo = mocker.patch(f"{SVC}.checklist_repository.list_by_chat", return_value=[])
    service.list_checklists(user, chat_id=5)
    repo.assert_called_once_with(source_chat_id=5)


def test_list_checklists_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{CRUD}.chat_repository.get_by_id", return_value=None)
    with pytest.raises(ChatNotFoundException):
        service.list_checklists(user, chat_id=999)


def test_list_checklists_not_chat_member_raises_403(mocker):
    user = make_user(user_id=1)
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{CRUD}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{CRUD}.membership_repository.is_active_member", return_value=False)
    with pytest.raises(ChatAccessDeniedException):
        service.list_checklists(user, chat_id=5)


# ══════════════════════════════════════════════════════════════════════════════
# list_all_checklists (admin)
# ══════════════════════════════════════════════════════════════════════════════

def test_list_all_checklists_calls_repo(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    repo = mocker.patch(f"{SVC}.checklist_repository.list_all", return_value=[])
    service.list_all_checklists(user)
    repo.assert_called_once_with()


# ══════════════════════════════════════════════════════════════════════════════
# get_own_checklist (used for export — any active member)
# ══════════════════════════════════════════════════════════════════════════════

def test_get_own_checklist_creator_has_access(mocker):
    user = make_user(user_id=1)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, checklist=cl)
    assert service.get_own_checklist(user, 1) is cl


def test_get_own_checklist_reader_member_has_access(mocker):
    user = make_user(user_id=2)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, checklist=cl, is_member=True)
    assert service.get_own_checklist(user, 1) is cl


def test_get_own_checklist_non_member_raises_403(mocker):
    user = make_user(user_id=2)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    _patch_access(mocker, checklist=cl, is_member=False)
    with pytest.raises(ChecklistAccessDeniedException):
        service.get_own_checklist(user, 1)


def test_get_own_checklist_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.checklist_repository.get_by_id", return_value=None)
    with pytest.raises(ChecklistNotFoundException):
        service.get_own_checklist(user, 999)


# ══════════════════════════════════════════════════════════════════════════════
# get_checklist_admin_export — bypasses access checks (admin only)
# ══════════════════════════════════════════════════════════════════════════════

def test_get_checklist_admin_export_returns_without_access_check(mocker):
    """Admin export ignores creator/membership entirely."""
    user = make_user(user_id=999)  # neither creator nor member
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=10)
    mocker.patch("core.authorization.access.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.checklist_repository.get_by_id", return_value=cl)
    is_member = mocker.patch(f"{ACCESS}.membership_repository.is_active_member")
    result = service.get_checklist_admin_export(user, 1)
    assert result is cl
    is_member.assert_not_called()


def test_get_checklist_admin_export_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.checklist_repository.get_by_id", return_value=None)
    with pytest.raises(ChecklistNotFoundException):
        service.get_checklist_admin_export(user, 999)


# ══════════════════════════════════════════════════════════════════════════════
# generate_checklist (async)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_generate_checklist_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=None)
    with pytest.raises(ChatNotFoundException):
        await service.generate_checklist(user, "x", chat_id=99)
