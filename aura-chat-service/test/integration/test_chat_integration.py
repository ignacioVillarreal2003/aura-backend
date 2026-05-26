import pytest
from django.utils import timezone

from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.models.chat import Chat
from apps.chat.services.chat_service import chat_service
from apps.membership.models.chat_membership import ChatMembership
from apps.message.models.chat_message import ChatMessage
from apps.message.repositories.message_repository import message_repository

from .conftest import make_user

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# create_chat
# ---------------------------------------------------------------------------

def test_create_chat_persists_to_db(owner):
    chat = chat_service.create_chat(owner, name="My Chat")
    assert Chat.objects.filter(id=chat.id, name="My Chat").exists()


def test_create_chat_creates_owner_membership(owner):
    chat = chat_service.create_chat(owner, name="My Chat")
    membership = ChatMembership.objects.get(chat_id=chat.id, member_id=owner.id)
    assert membership.role == ChatMembership.Role.OWNER
    assert membership.status == ChatMembership.Status.ACTIVE


def test_create_chat_with_tags(owner):
    chat = chat_service.create_chat(owner, name="Tagged", tags=["ai", "docs"])
    chat.refresh_from_db()
    assert chat.tags == ["ai", "docs"]


def test_create_chat_sets_created_by(owner):
    chat = chat_service.create_chat(owner, name="Audit Test")
    assert chat.created_by == owner.id


# ---------------------------------------------------------------------------
# update_chat
# ---------------------------------------------------------------------------

def test_update_chat_persists_changes(owner, chat):
    chat_service.update_chat(owner, chat.id, name="Renamed", system_prompt="Be concise.")
    chat.refresh_from_db()
    assert chat.name == "Renamed"
    assert chat.system_prompt == "Be concise."


def test_update_chat_sets_updated_by(owner, chat):
    chat_service.update_chat(owner, chat.id, name="Updated")
    chat.refresh_from_db()
    assert chat.updated_by == owner.id


def test_update_chat_non_owner_raises(chat, other_user):
    with pytest.raises(ChatAccessDeniedException):
        chat_service.update_chat(other_user, chat.id, name="Hack")


def test_update_chat_not_found_raises(owner):
    with pytest.raises(ChatNotFoundException):
        chat_service.update_chat(owner, 999999, name="Ghost")


# ---------------------------------------------------------------------------
# delete_chat
# ---------------------------------------------------------------------------

def test_delete_chat_soft_deletes_chat(owner, chat):
    chat_id = chat.id
    chat_service.delete_chat(owner, chat_id)
    assert not Chat.objects.filter(id=chat_id).exists()
    assert Chat.objects.all_with_deleted().filter(id=chat_id, deleted_at__isnull=False).exists()


def test_delete_chat_soft_deletes_memberships(owner, chat):
    chat_id = chat.id
    chat_service.delete_chat(owner, chat_id)
    assert not ChatMembership.objects.filter(chat_id=chat_id).exists()
    assert ChatMembership.objects.all_with_deleted().filter(
        chat_id=chat_id, deleted_at__isnull=False
    ).exists()


def test_delete_chat_soft_deletes_messages(owner, chat, user_message):
    chat_id = chat.id
    chat_service.delete_chat(owner, chat_id)
    assert not ChatMessage.objects.filter(chat_id=chat_id).exists()
    assert ChatMessage.objects.all_with_deleted().filter(
        chat_id=chat_id, deleted_at__isnull=False
    ).exists()


def test_delete_chat_non_owner_raises(chat, other_user):
    with pytest.raises(ChatAccessDeniedException):
        chat_service.delete_chat(other_user, chat.id)


# ---------------------------------------------------------------------------
# list_chats
# ---------------------------------------------------------------------------

def test_list_chats_returns_own_active_chats(owner):
    c1 = chat_service.create_chat(owner, name="Chat A")
    c2 = chat_service.create_chat(owner, name="Chat B")
    ids = list(chat_service.list_chats(owner).values_list("id", flat=True))
    assert c1.id in ids
    assert c2.id in ids


def test_list_chats_excludes_other_users_chats(owner, other_user):
    chat_service.create_chat(other_user, name="Other's Chat")
    ids = list(chat_service.list_chats(owner).values_list("id", flat=True))
    other_ids = list(chat_service.list_chats(other_user).values_list("id", flat=True))
    assert not any(i in ids for i in other_ids)


def test_list_chats_search_filters_by_name(owner):
    chat_service.create_chat(owner, name="Alpha Chat")
    chat_service.create_chat(owner, name="Beta Chat")
    results = list(chat_service.list_chats(owner, search="Alpha").values_list("name", flat=True))
    assert all("alpha" in n.lower() for n in results)


# ---------------------------------------------------------------------------
# archive / unarchive
# ---------------------------------------------------------------------------

def test_archive_chat_sets_archived_at(owner, chat):
    chat_service.archive_chats(owner, chat_ids=[chat.id])
    membership = ChatMembership.objects.get(chat_id=chat.id, member_id=owner.id)
    assert membership.archived_at is not None


def test_unarchive_chat_clears_archived_at(owner, chat):
    chat_service.archive_chats(owner, chat_ids=[chat.id])
    chat_service.unarchive_chats(owner, chat_ids=[chat.id])
    membership = ChatMembership.objects.get(chat_id=chat.id, member_id=owner.id)
    assert membership.archived_at is None


def test_archived_chat_appears_in_archived_list(owner, chat):
    chat_service.archive_chats(owner, chat_ids=[chat.id])
    archived_ids = list(
        chat_service.list_archived_chats(owner).values_list("id", flat=True)
    )
    assert chat.id in archived_ids


# ---------------------------------------------------------------------------
# pin / unpin
# ---------------------------------------------------------------------------

def test_pin_chat_sets_pinned_at(owner, chat):
    chat_service.pin_chat(owner, chat.id)
    membership = ChatMembership.objects.get(chat_id=chat.id, member_id=owner.id)
    assert membership.pinned_at is not None


def test_unpin_chat_clears_pinned_at(owner, chat):
    chat_service.pin_chat(owner, chat.id)
    chat_service.unpin_chat(owner, chat.id)
    membership = ChatMembership.objects.get(chat_id=chat.id, member_id=owner.id)
    assert membership.pinned_at is None


# ---------------------------------------------------------------------------
# lock / unlock
# ---------------------------------------------------------------------------

def test_lock_chat_sets_is_locked(owner, chat):
    chat_service.lock_chat(owner, chat.id)
    chat.refresh_from_db()
    assert chat.is_locked is True


def test_unlock_chat_clears_is_locked(owner, chat):
    chat_service.lock_chat(owner, chat.id)
    chat_service.unlock_chat(owner, chat.id)
    chat.refresh_from_db()
    assert chat.is_locked is False


def test_lock_chat_non_owner_raises(chat, other_user):
    with pytest.raises(ChatAccessDeniedException):
        chat_service.lock_chat(other_user, chat.id)


# ---------------------------------------------------------------------------
# mute / unmute
# ---------------------------------------------------------------------------

def test_mute_chat_sets_muted_until(owner, chat):
    until = timezone.now() + timezone.timedelta(hours=1)
    chat_service.mute_chat(owner, chat.id, muted_until=until)
    membership = ChatMembership.objects.get(chat_id=chat.id, member_id=owner.id)
    assert membership.muted_until is not None


def test_unmute_chat_clears_muted_until(owner, chat):
    until = timezone.now() + timezone.timedelta(hours=1)
    chat_service.mute_chat(owner, chat.id, muted_until=until)
    chat_service.unmute_chat(owner, chat.id)
    membership = ChatMembership.objects.get(chat_id=chat.id, member_id=owner.id)
    assert membership.muted_until is None
