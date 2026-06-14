"""
Chat service — business-logic tests

Authorization model under test
------------------------------
* **Global / chat-wide mutations** (update, delete, lock, unlock): allowed for the
  chat creator (``chat.created_by``) **or** any active member whose membership role
  is ``owner``. Everyone else gets ``ChatAccessDeniedException`` (403).
* **Personal actions** (get, pin/unpin, archive/unarchive): only require
  the caller to be an *active member* of the chat.
* **Create / list-mine / list-all (admin)**: gated by permissions only, no ownership.
"""
import pytest

from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.services.chat_service import ChatService
from core.exceptions.base import InsufficientPermissionsException
from test.conftest import make_chat, make_membership, make_user

SVC = "apps.chat.services.chat_service"

service = ChatService()


# ---------------------------------------------------------------------------
# Patch helpers
# ---------------------------------------------------------------------------

def _patch_perms(mocker):
    mocker.patch(f"{SVC}.AccessControl.require_permissions")


def _patch_atomic(mocker):
    """Make @transaction.atomic / `with transaction.atomic()` no-ops without a real DB."""
    mocker.patch("django.db.transaction.Atomic.__enter__", return_value=None)
    mocker.patch("django.db.transaction.Atomic.__exit__", return_value=False)


def _patch_chat(mocker, chat):
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=chat)


def _patch_chat_for_update(mocker, chat):
    mocker.patch(f"{SVC}.chat_repository.get_by_id_for_update", return_value=chat)


def _patch_no_broadcast(mocker):
    mocker.patch(f"{SVC}._broadcast_chat_locked_changed")


def _patch_lock_notifications(mocker):
    """lock_chat notifies the other active members after locking. Stub the member
    lookup (otherwise it hits the real DB) and the outbound notification client."""
    mocker.patch(f"{SVC}.membership_repository.get_active_member_ids", return_value=[])
    mocker.patch(f"{SVC}.notification_client.emit_event")


def _patch_delete_side_effects(mocker):
    """delete_chat fans out via ``transaction.on_commit``; run those callbacks
    immediately and stub the ones that touch Redis / channels / other services.

    Returns the mock for the cross-service document cleanup so callers can
    assert the chat deletion forwards the right chat id and acting user.
    """
    mocker.patch("django.db.transaction.on_commit", side_effect=lambda fn, *a, **k: fn())
    mocker.patch(f"{SVC}._release_ai_lock")
    mocker.patch(f"{SVC}._broadcast_chat_deleted")
    return mocker.patch(f"{SVC}.document_processing_client.delete_documents_by_chat")


# ══════════════════════════════════════════════════════════════════════════════
# create_chat
# ══════════════════════════════════════════════════════════════════════════════

def test_create_chat_creates_chat_and_owner_membership(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=10, created_by=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    create_chat = mocker.patch(f"{SVC}.chat_repository.create", return_value=chat)
    create_member = mocker.patch(f"{SVC}.membership_repository.create")

    result = service.create_chat(user, name="My Chat", tags=["a"])

    assert result is chat
    create_chat.assert_called_once()
    _, ckwargs = create_chat.call_args
    assert ckwargs["created_by"] == 1
    assert ckwargs["name"] == "My Chat"
    # The creator is registered as an active owner member of the new chat.
    _, mkwargs = create_member.call_args
    assert mkwargs["member_id"] == 1
    assert mkwargs["chat_id"] == 10
    assert mkwargs["role"] == "owner"
    assert mkwargs["status"] == "active"


def test_create_chat_without_permission_raises_403(mocker):
    user = make_user(user_id=1, permissions=())
    _patch_atomic(mocker)
    mocker.patch(
        f"{SVC}.AccessControl.require_permissions",
        side_effect=InsufficientPermissionsException(),
    )
    with pytest.raises(InsufficientPermissionsException):
        service.create_chat(user, name="Nope")


# ══════════════════════════════════════════════════════════════════════════════
# get_chat  (personal — active membership required)
# ══════════════════════════════════════════════════════════════════════════════

def test_get_chat_active_member_returns_chat_with_membership_fields(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    membership = make_membership(
        member_id=2, chat_id=1, status="active",
        pinned_at=None, archived_at=None,
    )
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(
        f"{SVC}.membership_repository.get_by_chat_and_member",
        return_value=membership,
    )

    result = service.get_chat(user, chat_id=1)

    assert result is chat
    assert result.pinned_at == membership.pinned_at
    assert result.archived_at == membership.archived_at


def test_get_chat_not_found_raises_404(mocker):
    user = make_user(user_id=2)
    _patch_perms(mocker)
    _patch_chat(mocker, None)
    with pytest.raises(ChatNotFoundException):
        service.get_chat(user, chat_id=999)


def test_get_chat_non_member_raises_403(mocker):
    user = make_user(user_id=99)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.get_by_chat_and_member", return_value=None)
    with pytest.raises(ChatAccessDeniedException):
        service.get_chat(user, chat_id=1)


def test_get_chat_inactive_member_raises_403(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    membership = make_membership(member_id=2, chat_id=1, status="inactive")
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.get_by_chat_and_member", return_value=membership)
    with pytest.raises(ChatAccessDeniedException):
        service.get_chat(user, chat_id=1)


# ══════════════════════════════════════════════════════════════════════════════
# list_chats / list_own_chats / list_all_chats
# ══════════════════════════════════════════════════════════════════════════════

def test_list_chats_forwards_to_repository(mocker):
    user = make_user(user_id=3)
    _patch_perms(mocker)
    qs = object()
    repo = mocker.patch(f"{SVC}.chat_repository.get_chats_for_member", return_value=qs)
    result = service.list_chats(user, search="x", ordering="name", tags=["t"])
    assert result is qs
    repo.assert_called_once_with(member_id=3, search="x", ordering="name", tags=["t"])


def test_list_chats_default_ordering(mocker):
    user = make_user(user_id=3)
    _patch_perms(mocker)
    repo = mocker.patch(f"{SVC}.chat_repository.get_chats_for_member", return_value=[])
    service.list_chats(user)
    _, kwargs = repo.call_args
    assert kwargs["ordering"] == "-last_message_at"


def test_list_own_chats_filters_by_creator(mocker):
    user = make_user(user_id=7)
    _patch_perms(mocker)
    repo = mocker.patch(f"{SVC}.chat_repository.get_chats_created_by", return_value=[])
    service.list_own_chats(user)
    _, kwargs = repo.call_args
    assert kwargs["user_id"] == 7
    assert kwargs["ordering"] == "-created_at"


def test_list_all_chats_admin_forwards(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    qs = object()
    repo = mocker.patch(f"{SVC}.chat_repository.list_all", return_value=qs)
    result = service.list_all_chats(user, search="q")
    assert result is qs
    _, kwargs = repo.call_args
    assert kwargs["search"] == "q"
    assert kwargs["ordering"] == "-created_at"


def test_list_archived_chats_forwards(mocker):
    user = make_user(user_id=2)
    _patch_perms(mocker)
    repo = mocker.patch(f"{SVC}.chat_repository.get_archived_chats_for_member", return_value=[])
    service.list_archived_chats(user, tags=["work"])
    _, kwargs = repo.call_args
    assert kwargs["member_id"] == 2
    assert kwargs["tags"] == ["work"]


# ══════════════════════════════════════════════════════════════════════════════
# update_chat  (global — creator OR membership owner)
# ══════════════════════════════════════════════════════════════════════════════

def test_update_chat_creator_can_update(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    updated = make_chat(chat_id=1, created_by=1, name="Updated")
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    is_owner = mocker.patch(f"{SVC}.membership_repository.is_chat_owner")
    repo = mocker.patch(f"{SVC}.chat_repository.update", return_value=updated)

    result = service.update_chat(user, chat_id=1, name="Updated")

    assert result.name == "Updated"
    repo.assert_called_once()
    # Creator shortcut: no need to consult membership role.
    is_owner.assert_not_called()


def test_update_chat_owner_member_can_update(mocker):
    """A non-creator whose membership role is owner may update the chat."""
    user = make_user(user_id=5)
    chat = make_chat(chat_id=1, created_by=1)
    updated = make_chat(chat_id=1, created_by=1, name="Updated")
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=True)
    mocker.patch(f"{SVC}.chat_repository.update", return_value=updated)

    result = service.update_chat(user, chat_id=1, name="Updated")
    assert result.name == "Updated"


def test_update_chat_regular_member_raises_403(mocker):
    """An active member that is neither creator nor owner cannot update."""
    user = make_user(user_id=5)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    with pytest.raises(ChatAccessDeniedException):
        service.update_chat(user, chat_id=1, name="Updated")


def test_update_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, None)
    with pytest.raises(ChatNotFoundException):
        service.update_chat(user, chat_id=999, name="X")


def test_update_chat_passes_updated_by(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    repo = mocker.patch(f"{SVC}.chat_repository.update", return_value=chat)
    service.update_chat(user, chat_id=1, name="X")
    _, kwargs = repo.call_args
    assert kwargs["updated_by"] == 1
    assert kwargs["name"] == "X"


# ══════════════════════════════════════════════════════════════════════════════
# delete_chat  (global — creator OR membership owner)
# ══════════════════════════════════════════════════════════════════════════════

def test_delete_chat_creator_soft_deletes_everything(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    mocker.patch(f"{SVC}.share_link_repository.deactivate_by_chat")
    del_members = mocker.patch(f"{SVC}.membership_repository.soft_delete_by_chat")
    clear_artifacts = mocker.patch("apps.artifact.services.artifact_service.clear_chat_artifacts")
    del_chat = mocker.patch(f"{SVC}.chat_repository.soft_delete")
    doc_cleanup = _patch_delete_side_effects(mocker)

    service.delete_chat(user, chat_id=1)

    del_members.assert_called_once_with(1, deleted_by=1)
    clear_artifacts.assert_called_once_with(1, deleted_by=1)
    del_chat.assert_called_once_with(chat, deleted_by=1)
    doc_cleanup.assert_called_once_with(1, user)


def test_delete_chat_owner_member_can_delete(mocker):
    user = make_user(user_id=5)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=True)
    mocker.patch(f"{SVC}.share_link_repository.deactivate_by_chat")
    mocker.patch(f"{SVC}.membership_repository.soft_delete_by_chat")
    mocker.patch("apps.artifact.services.artifact_service.clear_chat_artifacts")
    del_chat = mocker.patch(f"{SVC}.chat_repository.soft_delete")
    _patch_delete_side_effects(mocker)
    service.delete_chat(user, chat_id=1)
    del_chat.assert_called_once()


def test_delete_chat_triggers_document_cleanup_in_other_service(mocker):
    """Deleting a chat must ask the document-processing service to drop that
    chat's documents, forwarding the acting user so its bearer token can be
    used downstream."""
    user = make_user(user_id=1)
    chat = make_chat(chat_id=42, created_by=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    mocker.patch(f"{SVC}.share_link_repository.deactivate_by_chat")
    mocker.patch(f"{SVC}.membership_repository.soft_delete_by_chat")
    mocker.patch("apps.artifact.services.artifact_service.clear_chat_artifacts")
    mocker.patch(f"{SVC}.chat_repository.soft_delete")
    doc_cleanup = _patch_delete_side_effects(mocker)

    service.delete_chat(user, chat_id=42)

    doc_cleanup.assert_called_once_with(42, user)


def test_delete_chat_regular_member_raises_403(mocker):
    user = make_user(user_id=5)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    del_chat = mocker.patch(f"{SVC}.chat_repository.soft_delete")
    with pytest.raises(ChatAccessDeniedException):
        service.delete_chat(user, chat_id=1)
    del_chat.assert_not_called()


def test_delete_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, None)
    with pytest.raises(ChatNotFoundException):
        service.delete_chat(user, chat_id=999)


# ══════════════════════════════════════════════════════════════════════════════
# lock_chat / unlock_chat  (global — creator OR membership owner)
# ══════════════════════════════════════════════════════════════════════════════

def test_lock_chat_creator_can_lock(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1, is_locked=False)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    _patch_no_broadcast(mocker)
    _patch_lock_notifications(mocker)
    repo = mocker.patch(f"{SVC}.chat_repository.update", return_value=chat)
    service.lock_chat(user, chat_id=1)
    _, kwargs = repo.call_args
    assert kwargs["is_locked"] is True


def test_lock_chat_owner_member_can_lock(mocker):
    user = make_user(user_id=5)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    _patch_no_broadcast(mocker)
    _patch_lock_notifications(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=True)
    repo = mocker.patch(f"{SVC}.chat_repository.update", return_value=chat)
    service.lock_chat(user, chat_id=1)
    repo.assert_called_once()


def test_lock_chat_regular_member_raises_403(mocker):
    user = make_user(user_id=5)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    _patch_no_broadcast(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    repo = mocker.patch(f"{SVC}.chat_repository.update")
    with pytest.raises(ChatAccessDeniedException):
        service.lock_chat(user, chat_id=1)
    repo.assert_not_called()


def test_lock_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, None)
    _patch_no_broadcast(mocker)
    with pytest.raises(ChatNotFoundException):
        service.lock_chat(user, chat_id=999)


def test_lock_chat_broadcasts_locked_state(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    _patch_lock_notifications(mocker)
    mocker.patch(f"{SVC}.chat_repository.update", return_value=chat)
    broadcast = mocker.patch(f"{SVC}._broadcast_chat_locked_changed")
    service.lock_chat(user, chat_id=1)
    broadcast.assert_called_once_with(1, is_locked=True, by=1)


def test_unlock_chat_creator_can_unlock(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1, is_locked=True)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    _patch_no_broadcast(mocker)
    repo = mocker.patch(f"{SVC}.chat_repository.update", return_value=chat)
    service.unlock_chat(user, chat_id=1)
    _, kwargs = repo.call_args
    assert kwargs["is_locked"] is False


def test_unlock_chat_owner_member_can_unlock(mocker):
    user = make_user(user_id=5)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    _patch_no_broadcast(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=True)
    repo = mocker.patch(f"{SVC}.chat_repository.update", return_value=chat)
    service.unlock_chat(user, chat_id=1)
    repo.assert_called_once()


def test_unlock_chat_regular_member_raises_403(mocker):
    user = make_user(user_id=5)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    _patch_no_broadcast(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    with pytest.raises(ChatAccessDeniedException):
        service.unlock_chat(user, chat_id=1)


def test_unlock_chat_broadcasts_unlocked_state(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, chat)
    mocker.patch(f"{SVC}.chat_repository.update", return_value=chat)
    broadcast = mocker.patch(f"{SVC}._broadcast_chat_locked_changed")
    service.unlock_chat(user, chat_id=1)
    broadcast.assert_called_once_with(1, is_locked=False, by=1)


def test_unlock_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    _patch_atomic(mocker)
    _patch_chat_for_update(mocker, None)
    _patch_no_broadcast(mocker)
    with pytest.raises(ChatNotFoundException):
        service.unlock_chat(user, chat_id=999)


# ══════════════════════════════════════════════════════════════════════════════
# archive_chats / unarchive_chats  (personal — active membership on every id)
# ══════════════════════════════════════════════════════════════════════════════

def test_archive_chats_returns_count(mocker):
    user = make_user(user_id=2)
    _patch_perms(mocker)
    mocker.patch(
        f"{SVC}.membership_repository.get_active_chat_ids_for_member",
        return_value={1, 2},
    )
    mocker.patch(f"{SVC}.membership_repository.archive_chats", return_value=2)
    assert service.archive_chats(user, chat_ids=[1, 2]) == 2


def test_archive_chats_inaccessible_id_raises_403(mocker):
    user = make_user(user_id=2)
    _patch_perms(mocker)
    mocker.patch(
        f"{SVC}.membership_repository.get_active_chat_ids_for_member",
        return_value={1},
    )
    archive = mocker.patch(f"{SVC}.membership_repository.archive_chats")
    with pytest.raises(ChatAccessDeniedException):
        service.archive_chats(user, chat_ids=[1, 2])
    archive.assert_not_called()


def test_unarchive_chats_returns_count(mocker):
    user = make_user(user_id=2)
    _patch_perms(mocker)
    mocker.patch(
        f"{SVC}.membership_repository.get_active_chat_ids_for_member",
        return_value={1},
    )
    mocker.patch(f"{SVC}.membership_repository.unarchive_chats", return_value=1)
    assert service.unarchive_chats(user, chat_ids=[1]) == 1


def test_unarchive_chats_inaccessible_id_raises_403(mocker):
    user = make_user(user_id=2)
    _patch_perms(mocker)
    mocker.patch(
        f"{SVC}.membership_repository.get_active_chat_ids_for_member",
        return_value=set(),
    )
    with pytest.raises(ChatAccessDeniedException):
        service.unarchive_chats(user, chat_ids=[5])


# ══════════════════════════════════════════════════════════════════════════════
# pin_chat / unpin_chat  (personal — active membership)
# ══════════════════════════════════════════════════════════════════════════════

def test_pin_chat_active_member_pins(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=True)
    pin = mocker.patch(f"{SVC}.membership_repository.pin")
    service.pin_chat(user, chat_id=1)
    pin.assert_called_once_with(chat_id=1, member_id=2)


def test_pin_chat_not_found_raises_404(mocker):
    user = make_user(user_id=2)
    _patch_perms(mocker)
    _patch_chat(mocker, None)
    with pytest.raises(ChatNotFoundException):
        service.pin_chat(user, chat_id=999)


def test_pin_chat_non_member_raises_403(mocker):
    user = make_user(user_id=99)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=False)
    with pytest.raises(ChatAccessDeniedException):
        service.pin_chat(user, chat_id=1)


def test_unpin_chat_active_member_unpins(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=True)
    unpin = mocker.patch(f"{SVC}.membership_repository.unpin")
    service.unpin_chat(user, chat_id=1)
    unpin.assert_called_once_with(chat_id=1, member_id=2)


def test_unpin_chat_non_member_raises_403(mocker):
    user = make_user(user_id=99)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=False)
    with pytest.raises(ChatAccessDeniedException):
        service.unpin_chat(user, chat_id=1)


def test_unpin_chat_not_found_raises_404(mocker):
    user = make_user(user_id=2)
    _patch_perms(mocker)
    _patch_chat(mocker, None)
    with pytest.raises(ChatNotFoundException):
        service.unpin_chat(user, chat_id=999)


