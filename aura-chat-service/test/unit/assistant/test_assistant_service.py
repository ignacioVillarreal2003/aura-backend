import pytest

from apps.assistant.exceptions import (
    AssistantAlreadyExistsException,
    AssistantInactiveException,
    AssistantNotFoundException,
)
from apps.assistant.services.assistant_service import AssistantService
from test.conftest import make_assistant, make_chat, make_user

SVC = "apps.assistant.services.assistant_service"
CHAT_SVC = "apps.chat.services.chat_service"

service = AssistantService()


@pytest.fixture(autouse=True)
def _patch_atomic(mocker):
    """create/update/start_chat wrap repo writes in transaction.atomic(); make it
    a no-op so the mock-only unit tests don't try to open a real DB connection."""
    mocker.patch("django.db.transaction.Atomic.__enter__", return_value=None)
    mocker.patch("django.db.transaction.Atomic.__exit__", return_value=False)


def _patch_perms(mocker):
    mocker.patch(f"{SVC}.AccessControl.require_permissions")


# ══════════════════════════════════════════════════════════════════════════════
# create_assistant
# ══════════════════════════════════════════════════════════════════════════════

def test_create_assistant_success(mocker):
    user = make_user(user_id=1)
    assistant = make_assistant()
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.exists_with_name", return_value=False)
    mocker.patch(f"{SVC}.assistant_repository.create", return_value=assistant)
    result = service.create_assistant(
        user, name="Asistente Alfa", description="Desc",
        system_prompt="Sé útil.", avatar_emoji="🤖", is_active=True,
    )
    assert result is assistant


def test_create_assistant_name_conflict_raises_409(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.exists_with_name", return_value=True)
    with pytest.raises(AssistantAlreadyExistsException):
        service.create_assistant(
            user, name="Duplicado", description="",
            system_prompt="Sé útil.", avatar_emoji="", is_active=True,
        )


def test_create_assistant_calls_repo_with_all_fields(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.exists_with_name", return_value=False)
    create = mocker.patch(f"{SVC}.assistant_repository.create", return_value=make_assistant())
    service.create_assistant(
        user, name="X", description="D",
        system_prompt="Prompt", avatar_emoji="⚡", is_active=False,
        response_style="conciso",
    )
    _, kwargs = create.call_args
    assert kwargs["name"] == "X"
    assert kwargs["system_prompt"] == "Prompt"
    assert kwargs["is_active"] is False
    assert kwargs["response_style"] == "conciso"
    assert kwargs["user_id"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# list_active_assistants / list_all_assistants
# ══════════════════════════════════════════════════════════════════════════════

def test_list_active_assistants_passes_search(mocker):
    user = make_user()
    _patch_perms(mocker)
    repo = mocker.patch(f"{SVC}.assistant_repository.list_active", return_value=[])
    service.list_active_assistants(user, search="alfa")
    repo.assert_called_once_with(search="alfa")


def test_list_active_assistants_no_search_passes_none(mocker):
    user = make_user()
    _patch_perms(mocker)
    repo = mocker.patch(f"{SVC}.assistant_repository.list_active", return_value=[])
    service.list_active_assistants(user)
    repo.assert_called_once_with(search=None)


def test_list_all_assistants_passes_search(mocker):
    user = make_user()
    _patch_perms(mocker)
    repo = mocker.patch(f"{SVC}.assistant_repository.list_all", return_value=[])
    service.list_all_assistants(user, search="beta")
    repo.assert_called_once_with(search="beta")


def test_list_all_assistants_no_search_passes_none(mocker):
    user = make_user()
    _patch_perms(mocker)
    repo = mocker.patch(f"{SVC}.assistant_repository.list_all", return_value=[])
    service.list_all_assistants(user)
    repo.assert_called_once_with(search=None)


# ══════════════════════════════════════════════════════════════════════════════
# get_assistant
# ══════════════════════════════════════════════════════════════════════════════

def test_get_assistant_returns_active_assistant(mocker):
    user = make_user()
    assistant = make_assistant(is_active=True)
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=assistant)
    result = service.get_assistant(user, 1)
    assert result is assistant


def test_get_assistant_not_found_raises_404(mocker):
    user = make_user()
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=None)
    with pytest.raises(AssistantNotFoundException):
        service.get_assistant(user, 999)


def test_get_assistant_inactive_raises_404(mocker):
    """Inactive assistant is treated as not found for regular users."""
    user = make_user()
    assistant = make_assistant(is_active=False)
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=assistant)
    with pytest.raises(AssistantNotFoundException):
        service.get_assistant(user, 1)


# ══════════════════════════════════════════════════════════════════════════════
# update_assistant
# ══════════════════════════════════════════════════════════════════════════════

def test_update_assistant_success(mocker):
    user = make_user()
    original = make_assistant(name="Viejo")
    updated = make_assistant(name="Nuevo")
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id_for_update", return_value=original)
    mocker.patch(f"{SVC}.assistant_repository.exists_with_name", return_value=False)
    mocker.patch(f"{SVC}.assistant_repository.update", return_value=updated)
    result = service.update_assistant(user, 1, name="Nuevo")
    assert result.name == "Nuevo"


def test_update_assistant_same_name_skips_conflict_check(mocker):
    """Updating to the same name should not trigger the uniqueness check."""
    user = make_user()
    assistant = make_assistant(name="Alfa")
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id_for_update", return_value=assistant)
    exists = mocker.patch(f"{SVC}.assistant_repository.exists_with_name", return_value=True)
    mocker.patch(f"{SVC}.assistant_repository.update", return_value=assistant)
    # Same name → condition `name != assistant.name` is False → no conflict check
    service.update_assistant(user, 1, name="Alfa")
    exists.assert_not_called()


def test_update_assistant_new_name_conflict_raises_409(mocker):
    user = make_user()
    assistant = make_assistant(name="Viejo")
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id_for_update", return_value=assistant)
    mocker.patch(f"{SVC}.assistant_repository.exists_with_name", return_value=True)
    with pytest.raises(AssistantAlreadyExistsException):
        service.update_assistant(user, 1, name="Nuevo")


def test_update_assistant_new_name_no_conflict_succeeds(mocker):
    user = make_user()
    original = make_assistant(name="Viejo")
    updated = make_assistant(name="Nuevo")
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id_for_update", return_value=original)
    mocker.patch(f"{SVC}.assistant_repository.exists_with_name", return_value=False)
    mocker.patch(f"{SVC}.assistant_repository.update", return_value=updated)
    result = service.update_assistant(user, 1, name="Nuevo")
    assert result.name == "Nuevo"


def test_update_assistant_not_found_raises_404(mocker):
    user = make_user()
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id_for_update", return_value=None)
    with pytest.raises(AssistantNotFoundException):
        service.update_assistant(user, 999, name="X")


def test_update_assistant_inactive_can_be_updated(mocker):
    """Admins can update inactive assistants (no is_active check in update)."""
    user = make_user()
    inactive = make_assistant(is_active=False)
    reactivated = make_assistant(is_active=True)
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id_for_update", return_value=inactive)
    mocker.patch(f"{SVC}.assistant_repository.exists_with_name", return_value=False)
    mocker.patch(f"{SVC}.assistant_repository.update", return_value=reactivated)
    result = service.update_assistant(user, 1, is_active=True)
    assert result.is_active is True


def test_update_assistant_forwards_updated_by_to_repo(mocker):
    """The acting user's id must be propagated to the repository as updated_by."""
    user = make_user(user_id=7)
    assistant = make_assistant(name="Alfa")
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id_for_update", return_value=assistant)
    mocker.patch(f"{SVC}.assistant_repository.exists_with_name", return_value=False)
    update = mocker.patch(f"{SVC}.assistant_repository.update", return_value=assistant)
    service.update_assistant(user, 1, description="Nueva descripción")
    _, kwargs = update.call_args
    assert kwargs["updated_by"] == 7


# ══════════════════════════════════════════════════════════════════════════════
# delete_assistant
# ══════════════════════════════════════════════════════════════════════════════

def test_delete_assistant_success(mocker):
    user = make_user(user_id=1)
    assistant = make_assistant()
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=assistant)
    soft_delete = mocker.patch(f"{SVC}.assistant_repository.soft_delete")
    service.delete_assistant(user, 1)
    soft_delete.assert_called_once_with(assistant, deleted_by=1)


def test_delete_assistant_not_found_raises_404(mocker):
    user = make_user()
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=None)
    with pytest.raises(AssistantNotFoundException):
        service.delete_assistant(user, 999)


def test_delete_inactive_assistant_succeeds(mocker):
    """Admins can delete inactive assistants — no is_active check."""
    user = make_user(user_id=1)
    inactive = make_assistant(is_active=False)
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=inactive)
    soft_delete = mocker.patch(f"{SVC}.assistant_repository.soft_delete")
    service.delete_assistant(user, 1)
    soft_delete.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# start_chat
# ══════════════════════════════════════════════════════════════════════════════

def test_start_chat_creates_new_chat_when_resume_false(mocker):
    user = make_user(user_id=1)
    assistant = make_assistant()
    chat = make_chat(chat_id=10)
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=assistant)
    mocker.patch(f"{CHAT_SVC}.chat_service.create_chat", return_value=chat)
    result_chat, is_new = service.start_chat(user, 1, resume=False)
    assert result_chat is chat
    assert is_new is True


def test_start_chat_default_resume_is_false(mocker):
    user = make_user()
    assistant = make_assistant()
    chat = make_chat()
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=assistant)
    mocker.patch(f"{CHAT_SVC}.chat_service.create_chat", return_value=chat)
    _, is_new = service.start_chat(user, 1)
    assert is_new is True


def test_start_chat_resume_true_returns_existing_chat(mocker):
    user = make_user(user_id=1)
    assistant = make_assistant()
    existing = make_chat(chat_id=5)
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=assistant)
    mocker.patch(f"{SVC}.chat_repository.get_latest_by_assistant", return_value=existing)
    result_chat, is_new = service.start_chat(user, 1, resume=True)
    assert result_chat is existing
    assert is_new is False


def test_start_chat_resume_true_no_existing_creates_new(mocker):
    user = make_user(user_id=1)
    assistant = make_assistant()
    new_chat = make_chat(chat_id=99)
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=assistant)
    mocker.patch(f"{SVC}.chat_repository.get_latest_by_assistant", return_value=None)
    mocker.patch(f"{CHAT_SVC}.chat_service.create_chat", return_value=new_chat)
    result_chat, is_new = service.start_chat(user, 1, resume=True)
    assert result_chat is new_chat
    assert is_new is True


def test_start_chat_assistant_not_found_raises_404(mocker):
    user = make_user()
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=None)
    with pytest.raises(AssistantNotFoundException):
        service.start_chat(user, 999)


def test_start_chat_inactive_assistant_raises_400(mocker):
    user = make_user()
    inactive = make_assistant(is_active=False)
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=inactive)
    with pytest.raises(AssistantInactiveException):
        service.start_chat(user, 1)


def test_start_chat_creates_chat_with_assistant_system_prompt(mocker):
    user = make_user(user_id=1)
    assistant = make_assistant(
        assistant_id=7,
        name="Experto en táctica",
        system_prompt="Analiza siempre el terreno.",
        response_style="conciso",
    )
    chat = make_chat(chat_id=20)
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=assistant)
    create_chat = mocker.patch(f"{CHAT_SVC}.chat_service.create_chat", return_value=chat)
    service.start_chat(user, 7, resume=False)
    _, kwargs = create_chat.call_args
    assert kwargs["system_prompt"] == "Analiza siempre el terreno."
    assert kwargs["response_style"] == "conciso"
    assert kwargs["source_assistant_id"] == 7


def test_start_chat_names_chat_after_assistant(mocker):
    """The created chat name is prefixed with the assistant's name."""
    user = make_user(user_id=1)
    assistant = make_assistant(assistant_id=3, name="Experto en táctica")
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=assistant)
    create_chat = mocker.patch(f"{CHAT_SVC}.chat_service.create_chat", return_value=make_chat())
    service.start_chat(user, 3, resume=False)
    _, kwargs = create_chat.call_args
    assert kwargs["name"].startswith("Experto en táctica — ")


def test_start_chat_does_not_check_existing_when_resume_false(mocker):
    """With resume=False, never queries for existing chats."""
    user = make_user()
    assistant = make_assistant()
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.assistant_repository.get_by_id", return_value=assistant)
    get_latest = mocker.patch(f"{SVC}.chat_repository.get_latest_by_assistant")
    mocker.patch(f"{CHAT_SVC}.chat_service.create_chat", return_value=make_chat())
    service.start_chat(user, 1, resume=False)
    get_latest.assert_not_called()
