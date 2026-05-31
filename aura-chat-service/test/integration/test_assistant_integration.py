import pytest

from apps.assistant.exceptions import (
    AssistantAlreadyExistsException,
    AssistantInactiveException,
    AssistantNotFoundException,
)
from apps.assistant.models import Assistant
from apps.assistant.services.assistant_service import assistant_service
from apps.chat.models.chat import Chat
from apps.membership.models.chat_membership import ChatMembership

pytestmark = pytest.mark.django_db


def _make_assistant(owner, **overrides):
    params = dict(
        name="Asistente Integración",
        description="Descripción",
        system_prompt="Sé útil.",
        avatar_emoji="🤖",
        is_active=True,
    )
    params.update(overrides)
    return assistant_service.create_assistant(owner, **params)


# ---------------------------------------------------------------------------
# create_assistant
# ---------------------------------------------------------------------------

def test_create_assistant_persists_to_db(owner):
    assistant = _make_assistant(owner, name="Nuevo")
    assert Assistant.objects.filter(id=assistant.id, name="Nuevo").exists()


def test_create_assistant_sets_created_by(owner):
    assistant = _make_assistant(owner)
    assert assistant.created_by == owner.id


def test_create_assistant_persists_all_fields(owner):
    assistant = _make_assistant(
        owner,
        name="Completo",
        description="Una descripción",
        system_prompt="Prompt fijo",
        response_style="conciso",
        avatar_emoji="⚡",
        is_active=False,
    )
    assistant.refresh_from_db()
    assert assistant.description == "Una descripción"
    assert assistant.system_prompt == "Prompt fijo"
    assert assistant.response_style == "conciso"
    assert assistant.avatar_emoji == "⚡"
    assert assistant.is_active is False


def test_create_assistant_duplicate_name_raises(owner):
    _make_assistant(owner, name="Repetido")
    with pytest.raises(AssistantAlreadyExistsException):
        _make_assistant(owner, name="Repetido")


# ---------------------------------------------------------------------------
# get_assistant
# ---------------------------------------------------------------------------

def test_get_assistant_returns_active(owner):
    assistant = _make_assistant(owner)
    result = assistant_service.get_assistant(owner, assistant.id)
    assert result.id == assistant.id


def test_get_assistant_not_found_raises(owner):
    with pytest.raises(AssistantNotFoundException):
        assistant_service.get_assistant(owner, 999999)


def test_get_assistant_inactive_raises_not_found(owner):
    assistant = _make_assistant(owner, is_active=False)
    with pytest.raises(AssistantNotFoundException):
        assistant_service.get_assistant(owner, assistant.id)


# ---------------------------------------------------------------------------
# list_active_assistants / list_all_assistants
# ---------------------------------------------------------------------------

def test_list_active_excludes_inactive(owner):
    active = _make_assistant(owner, name="Activo")
    inactive = _make_assistant(owner, name="Inactivo", is_active=False)
    ids = [a.id for a in assistant_service.list_active_assistants(owner)]
    assert active.id in ids
    assert inactive.id not in ids


def test_list_active_search_filters_by_name(owner):
    _make_assistant(owner, name="Alfa Buscador")
    _make_assistant(owner, name="Beta Distinto")
    names = [a.name for a in assistant_service.list_active_assistants(owner, search="alfa")]
    assert "Alfa Buscador" in names
    assert all("alfa" in n.lower() for n in names)


def test_list_all_includes_inactive(owner):
    inactive = _make_assistant(owner, name="Inactivo Listado", is_active=False)
    ids = [a.id for a in assistant_service.list_all_assistants(owner)]
    assert inactive.id in ids


# ---------------------------------------------------------------------------
# update_assistant  (exercises the repository's field-by-field update logic)
# ---------------------------------------------------------------------------

def test_update_assistant_persists_changes(owner):
    assistant = _make_assistant(owner, name="Viejo")
    assistant_service.update_assistant(owner, assistant.id, name="NuevoNombre")
    assistant.refresh_from_db()
    assert assistant.name == "NuevoNombre"


def test_update_assistant_sets_updated_by(owner):
    assistant = _make_assistant(owner)
    assistant_service.update_assistant(owner, assistant.id, description="Otra")
    assistant.refresh_from_db()
    assert assistant.updated_by == owner.id


def test_update_assistant_partial_only_changes_provided_fields(owner):
    assistant = _make_assistant(
        owner, name="Original", description="DescOrig", system_prompt="PromptOrig"
    )
    assistant_service.update_assistant(owner, assistant.id, description="DescNueva")
    assistant.refresh_from_db()
    assert assistant.description == "DescNueva"
    assert assistant.name == "Original"          # untouched
    assert assistant.system_prompt == "PromptOrig"  # untouched


def test_update_assistant_reactivates(owner):
    assistant = _make_assistant(owner, is_active=False)
    assistant_service.update_assistant(owner, assistant.id, is_active=True)
    assistant.refresh_from_db()
    assert assistant.is_active is True


def test_update_assistant_same_name_succeeds(owner):
    assistant = _make_assistant(owner, name="MismoNombre")
    result = assistant_service.update_assistant(
        owner, assistant.id, name="MismoNombre", description="cambiada"
    )
    assert result.description == "cambiada"


def test_update_assistant_duplicate_name_raises(owner):
    _make_assistant(owner, name="Ocupado")
    other = _make_assistant(owner, name="Libre")
    with pytest.raises(AssistantAlreadyExistsException):
        assistant_service.update_assistant(owner, other.id, name="Ocupado")


def test_update_assistant_not_found_raises(owner):
    with pytest.raises(AssistantNotFoundException):
        assistant_service.update_assistant(owner, 999999, name="Fantasma")


# ---------------------------------------------------------------------------
# delete_assistant  (soft delete)
# ---------------------------------------------------------------------------

def test_delete_assistant_soft_deletes(owner):
    assistant = _make_assistant(owner)
    assistant_id = assistant.id
    assistant_service.delete_assistant(owner, assistant_id)
    assert not Assistant.objects.filter(id=assistant_id).exists()
    assert Assistant.objects.all_with_deleted().filter(
        id=assistant_id, deleted_at__isnull=False
    ).exists()


def test_delete_assistant_sets_deleted_by(owner):
    assistant = _make_assistant(owner)
    assistant_id = assistant.id
    assistant_service.delete_assistant(owner, assistant_id)
    deleted = Assistant.objects.all_with_deleted().get(id=assistant_id)
    assert deleted.deleted_by == owner.id


def test_delete_assistant_not_found_raises(owner):
    with pytest.raises(AssistantNotFoundException):
        assistant_service.delete_assistant(owner, 999999)


# ---------------------------------------------------------------------------
# start_chat  (assistant → chat wiring, end-to-end)
# ---------------------------------------------------------------------------

def test_start_chat_creates_persisted_chat(owner):
    assistant = _make_assistant(owner)
    chat, is_new = assistant_service.start_chat(owner, assistant.id, resume=False)
    assert is_new is True
    assert Chat.objects.filter(id=chat.id).exists()


def test_start_chat_copies_prompt_and_links_assistant(owner):
    assistant = _make_assistant(
        owner, name="Táctico", system_prompt="Analiza el terreno.", response_style="conciso"
    )
    chat, _ = assistant_service.start_chat(owner, assistant.id, resume=False)
    chat.refresh_from_db()
    assert chat.system_prompt == "Analiza el terreno."
    assert chat.response_style == "conciso"
    assert chat.source_assistant_id == assistant.id


def test_start_chat_names_chat_after_assistant(owner):
    assistant = _make_assistant(owner, name="Táctico")
    chat, _ = assistant_service.start_chat(owner, assistant.id, resume=False)
    assert chat.name.startswith("Táctico — ")


def test_start_chat_adds_owner_membership(owner):
    assistant = _make_assistant(owner)
    chat, _ = assistant_service.start_chat(owner, assistant.id, resume=False)
    membership = ChatMembership.objects.get(chat_id=chat.id, member_id=owner.id)
    assert membership.role == ChatMembership.Role.OWNER
    assert membership.status == ChatMembership.Status.ACTIVE


def test_start_chat_resume_false_always_creates_new(owner):
    assistant = _make_assistant(owner)
    chat1, _ = assistant_service.start_chat(owner, assistant.id, resume=False)
    chat2, _ = assistant_service.start_chat(owner, assistant.id, resume=False)
    assert chat1.id != chat2.id


def test_start_chat_resume_returns_existing_without_duplicating(owner):
    assistant = _make_assistant(owner)
    first, is_new_first = assistant_service.start_chat(owner, assistant.id, resume=True)
    second, is_new_second = assistant_service.start_chat(owner, assistant.id, resume=True)
    assert is_new_first is True
    assert is_new_second is False
    assert second.id == first.id


def test_start_chat_inactive_assistant_raises(owner):
    assistant = _make_assistant(owner, is_active=False)
    with pytest.raises(AssistantInactiveException):
        assistant_service.start_chat(owner, assistant.id)


def test_start_chat_assistant_not_found_raises(owner):
    with pytest.raises(AssistantNotFoundException):
        assistant_service.start_chat(owner, 999999)
