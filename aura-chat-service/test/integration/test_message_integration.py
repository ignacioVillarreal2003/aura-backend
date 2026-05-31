import pytest

from apps.message.exceptions import (
    ChatLockedException,
    MessageAccessDeniedException,
    MessageDeleteForbiddenException,
    MessageNotFoundException,
    NotChatOwnerException,
    ReaderCannotSendMessageException,
)
from apps.message.models.chat_message import ChatMessage
from apps.message.repositories.message_repository import message_repository
from apps.message.services.message_service import message_service
from apps.membership.services.membership_service import membership_service
from apps.chat.services.chat_service import chat_service

from .conftest import make_user

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------

def test_send_message_persists_to_db(owner, chat):
    msg = message_service.send_message(owner, chat.id, text="Hello!")
    assert ChatMessage.objects.filter(id=msg.id, message="Hello!").exists()


def test_send_message_sets_sender_type_user(owner, chat):
    msg = message_service.send_message(owner, chat.id, text="Hi")
    assert msg.sender_type == ChatMessage.SenderType.USER


def test_send_message_sets_created_by(owner, chat):
    msg = message_service.send_message(owner, chat.id, text="Hi")
    assert msg.created_by == owner.id


def test_send_message_updates_chat_last_message_at(owner, chat):
    message_service.send_message(owner, chat.id, text="Hi")
    chat.refresh_from_db()
    assert chat.last_message_at is not None


def test_send_message_non_member_raises(chat, other_user):
    with pytest.raises(MessageAccessDeniedException):
        message_service.send_message(other_user, chat.id, text="Hack")


def test_send_message_reader_raises(owner, chat, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    membership_service.update_member(member_user, chat.id, member_user.id, new_status="active")
    membership_service.update_member_role(owner, chat.id, member_user.id, role="reader")
    with pytest.raises(ReaderCannotSendMessageException):
        message_service.send_message(member_user, chat.id, text="Cannot send")


def test_send_message_locked_chat_raises(owner, chat):
    chat_service.lock_chat(owner, chat.id)
    with pytest.raises(ChatLockedException):
        message_service.send_message(owner, chat.id, text="Blocked")


# ---------------------------------------------------------------------------
# get_messages
# ---------------------------------------------------------------------------

def test_get_messages_returns_messages_for_chat(owner, chat):
    message_service.send_message(owner, chat.id, text="Msg 1")
    message_service.send_message(owner, chat.id, text="Msg 2")
    messages = list(message_service.get_messages(owner, chat.id))
    texts = [m.message for m in messages]
    assert "Msg 1" in texts
    assert "Msg 2" in texts


def test_get_messages_excludes_deleted(owner, chat, user_message):
    user_message.delete(deleted_by=owner.id)
    messages = list(message_service.get_messages(owner, chat.id))
    assert user_message.id not in [m.id for m in messages]


def test_get_messages_non_member_raises(chat, other_user):
    with pytest.raises(MessageAccessDeniedException):
        list(message_service.get_messages(other_user, chat.id))


# ---------------------------------------------------------------------------
# delete_message
# ---------------------------------------------------------------------------

def test_delete_message_by_author_soft_deletes(owner, chat, user_message):
    message_service.delete_message(owner, chat.id, user_message.id)
    assert not ChatMessage.objects.filter(id=user_message.id).exists()
    assert ChatMessage.objects.all_with_deleted().filter(
        id=user_message.id, deleted_at__isnull=False
    ).exists()


def test_delete_message_by_chat_owner_soft_deletes(owner, chat, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    membership_service.update_member(member_user, chat.id, member_user.id, new_status="active")
    member_msg = message_repository.create(
        chat_id=chat.id,
        message="member msg",
        sender_type=ChatMessage.SenderType.USER,
        created_by=member_user.id,
    )
    message_service.delete_message(owner, chat.id, member_msg.id)
    assert not ChatMessage.objects.filter(id=member_msg.id).exists()


def test_delete_message_by_non_author_raises(owner, chat, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    membership_service.update_member(member_user, chat.id, member_user.id, new_status="active")
    owner_msg = message_repository.create(
        chat_id=chat.id,
        message="owner msg",
        sender_type=ChatMessage.SenderType.USER,
        created_by=owner.id,
    )
    with pytest.raises(MessageDeleteForbiddenException):
        message_service.delete_message(member_user, chat.id, owner_msg.id)


def test_delete_message_not_found_raises(owner, chat):
    with pytest.raises(MessageNotFoundException):
        message_service.delete_message(owner, chat.id, 999999)


# ---------------------------------------------------------------------------
# clear_history
# ---------------------------------------------------------------------------

def test_clear_history_soft_deletes_all_messages(owner, chat):
    message_service.send_message(owner, chat.id, text="Msg 1")
    message_service.send_message(owner, chat.id, text="Msg 2")
    message_service.clear_history(owner, chat.id)
    assert ChatMessage.objects.filter(chat_id=chat.id).count() == 0
    assert ChatMessage.objects.all_with_deleted().filter(
        chat_id=chat.id, deleted_at__isnull=False
    ).count() >= 2


def test_clear_history_non_owner_raises(owner, chat, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    membership_service.update_member(member_user, chat.id, member_user.id, new_status="active")
    with pytest.raises(NotChatOwnerException):
        message_service.clear_history(member_user, chat.id)
