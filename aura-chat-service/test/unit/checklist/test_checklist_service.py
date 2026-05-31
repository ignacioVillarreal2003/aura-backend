from unittest.mock import AsyncMock

import pytest

from apps.checklist.exceptions import (
    ChecklistAccessDeniedException,
    ChecklistNotFoundException,
    LLMServiceException,
)
from apps.checklist.services.checklist_service import ChecklistService, _items_to_sections
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import ChecklistGenerateResult
from core.exceptions.base import InsufficientPermissionsException
from test.conftest import make_checklist, make_message, make_user

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
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.checklist_repository.get_by_id", return_value=cl)
    is_member = mocker.patch(f"{SVC}.membership_repository.is_active_member")
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
# update_checklist — creator path + not found (access branches covered above)
# ══════════════════════════════════════════════════════════════════════════════

def test_update_creator_can_update_own_checklist(mocker):
    user = make_user(user_id=1)
    cl = make_checklist(cl_id=1, created_by=1, source_chat_id=None)
    updated = make_checklist(cl_id=1, title="Nuevo")
    _patch_access(mocker, checklist=cl)
    update = mocker.patch(f"{SVC}.checklist_repository.update", return_value=updated)
    result = service.update_checklist(user, 1, title="Nuevo")
    assert result.title == "Nuevo"
    _, kwargs = update.call_args
    assert kwargs["updated_by"] == 1


def test_update_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.checklist_repository.get_by_id", return_value=None)
    with pytest.raises(ChecklistNotFoundException):
        service.update_checklist(user, 999, title="X")


# ══════════════════════════════════════════════════════════════════════════════
# generate_checklist (async)
# ══════════════════════════════════════════════════════════════════════════════

def _llm_result(title="Checklist de mantenimiento", items=None, messages=None, fragments=None):
    return ChecklistGenerateResult(
        title=title,
        items=items if items is not None else [
            {"section": "Fase 1", "text": "Paso", "is_checked": False, "notes": "", "order": 0},
        ],
        messages=messages if messages is not None else [{"role": "human", "content": "x"}],
        fragments=fragments if fragments is not None else [{"content": "frag", "document": {}}],
    )


@pytest.mark.asyncio
async def test_generate_checklist_without_chat_creates_and_returns(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    items = [
        {"section": "Fase 1", "text": "Paso A", "is_checked": False, "notes": "", "order": 0},
        {"section": "Fase 2", "text": "Paso B", "is_checked": True, "notes": "n", "order": 0},
    ]
    result = _llm_result(items=items)
    mocker.patch(f"{SVC}.llm_client.generate_checklist", new_callable=AsyncMock, return_value=result)
    created = make_checklist(cl_id=5)
    create = mocker.patch(f"{SVC}.checklist_repository.create", return_value=created)
    checklist, messages, fragments = await service.generate_checklist(user, "Crea", "direct")
    assert checklist is created
    assert messages == result.messages
    assert fragments == result.fragments
    _, kwargs = create.call_args
    assert kwargs["source_chat_id"] is None
    assert kwargs["title"] == result.title
    assert kwargs["user_id"] == 1
    # sections were built from the flat items via _items_to_sections
    assert [s["title"] for s in kwargs["sections"]] == ["Fase 1", "Fase 2"]


@pytest.mark.asyncio
async def test_generate_checklist_no_chat_does_not_query_history(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.checklist_repository.create", return_value=make_checklist())
    recent = mocker.patch(f"{SVC}.message_repository.get_recent_messages")
    llm = mocker.patch(f"{SVC}.llm_client.generate_checklist", new_callable=AsyncMock, return_value=_llm_result())
    await service.generate_checklist(user, "Crea", "direct")
    recent.assert_not_called()
    _, kwargs = llm.call_args
    assert kwargs["messages"] == [{"role": "human", "content": "Crea"}]


@pytest.mark.asyncio
async def test_generate_checklist_with_chat_builds_history_with_role_mapping(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{SVC}.membership_repository.is_active_contributor", return_value=True)
    msgs = [
        make_message(msg_id=1, sender_type="user", message="pregunta"),
        make_message(msg_id=2, sender_type="system", message="respuesta"),
    ]
    mocker.patch(f"{SVC}.message_repository.get_recent_messages", return_value=msgs)
    llm = mocker.patch(f"{SVC}.llm_client.generate_checklist", new_callable=AsyncMock, return_value=_llm_result())
    mocker.patch(f"{SVC}.checklist_repository.create", return_value=make_checklist())
    await service.generate_checklist(user, "Crea", "direct", chat_id=10)
    _, kwargs = llm.call_args
    history = kwargs["messages"]
    roles = {h["content"]: h["role"] for h in history}
    assert roles["pregunta"] == "human"       # USER → human
    assert roles["respuesta"] == "assistant"  # SYSTEM → assistant
    assert history[-1] == {"role": "human", "content": "Crea"}


@pytest.mark.asyncio
async def test_generate_checklist_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=None)
    with pytest.raises(ChatNotFoundException):
        await service.generate_checklist(user, "x", "direct", chat_id=99)


@pytest.mark.asyncio
async def test_generate_checklist_non_contributor_raises_403(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=object())
    mocker.patch(f"{SVC}.membership_repository.is_active_contributor", return_value=False)
    with pytest.raises(ChatAccessDeniedException):
        await service.generate_checklist(user, "x", "direct", chat_id=10)


@pytest.mark.asyncio
async def test_generate_checklist_llm_http_error_raises_502(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(
        f"{SVC}.llm_client.generate_checklist",
        new_callable=AsyncMock,
        side_effect=HttpClientException("boom", status_code=503),
    )
    with pytest.raises(LLMServiceException):
        await service.generate_checklist(user, "x", "direct")


@pytest.mark.asyncio
async def test_generate_checklist_empty_title_raises_and_skips_create(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(
        f"{SVC}.llm_client.generate_checklist",
        new_callable=AsyncMock,
        return_value=_llm_result(title="   "),
    )
    create = mocker.patch(f"{SVC}.checklist_repository.create")
    with pytest.raises(LLMServiceException):
        await service.generate_checklist(user, "x", "direct")
    create.assert_not_called()


@pytest.mark.asyncio
async def test_generate_checklist_empty_items_raises_and_skips_create(mocker):
    user = make_user(user_id=1)
    mocker.patch(f"{SVC}.AccessControl.require_permissions")
    mocker.patch(
        f"{SVC}.llm_client.generate_checklist",
        new_callable=AsyncMock,
        return_value=_llm_result(items=[]),
    )
    create = mocker.patch(f"{SVC}.checklist_repository.create")
    with pytest.raises(LLMServiceException):
        await service.generate_checklist(user, "x", "direct")
    create.assert_not_called()
