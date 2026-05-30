"""
Service-layer unit tests for the message module.

All dependencies (repositories, LLM client, channel layer) are mocked so tests
run without a database or external services.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.chat.exceptions import ChatNotFoundException
from apps.message.exceptions import (
    ChatLockedException,
    MessageAccessDeniedException,
    MessageDeleteForbiddenException,
    MessageNotFoundException,
    NoMessageToRegenerateException,
    NotAIMessageException,
    NotChatOwnerException,
    ReaderCannotSendMessageException,
)
from apps.message.services.bookmark_service import BookmarkService
from apps.message.services.feedback_service import FeedbackService
from apps.message.services.message_service import MessageService
from apps.message.services.pinned_message_service import PinnedMessageService
from apps.message.services.thread_service import ThreadService
from test.conftest import make_chat, make_message, make_pin, make_user, make_feedback, make_thread_reply

# ---------------------------------------------------------------------------
# Module path constants used for patching
# ---------------------------------------------------------------------------
MSG_SVC = "apps.message.services.message_service"
PIN_SVC = "apps.message.services.pinned_message_service"
BKM_SVC = "apps.message.services.bookmark_service"
FBK_SVC = "apps.message.services.feedback_service"
THR_SVC = "apps.message.services.thread_service"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_atomic(mocker):
    """Prevent @transaction.atomic from touching the database in unit tests."""
    mocker.patch("django.db.transaction.Atomic.__enter__", return_value=None)
    mocker.patch("django.db.transaction.Atomic.__exit__", return_value=False)
    mocker.patch(f"{MSG_SVC}.transaction.on_commit", side_effect=lambda fn: None)


def _user(user_id=1):
    return make_user(user_id=user_id)


def _chat(created_by=1, is_locked=False):
    return make_chat(created_by=created_by, is_locked=is_locked)


def _msg(msg_id=1, chat_id=1, created_by=1, sender_type="user"):
    m = make_message(msg_id=msg_id, chat_id=chat_id, created_by=created_by, sender_type=sender_type)
    m.delete = MagicMock()
    return m


# ===========================================================================
# MessageService
# ===========================================================================

class TestMessageServiceSendMessage:

    def test_send_message_happy_path(self, mocker):
        _patch_atomic(mocker)
        user = _user()
        chat = _chat()
        msg = _msg()
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=chat)
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.membership_repository.get_role", return_value="editor")
        mocker.patch(f"{MSG_SVC}.message_repository.create", return_value=msg)
        mocker.patch(f"{MSG_SVC}.chat_repository.touch_last_message_at")
        mocker.patch(f"{MSG_SVC}._broadcast_user_message_to_chat_group")

        svc = MessageService()
        result = svc.send_message(user, chat_id=1, text="Hello")

        assert result is msg

    def test_send_message_chat_not_found_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=None)
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)

        svc = MessageService()
        with pytest.raises(ChatNotFoundException):
            svc.send_message(_user(), chat_id=99, text="Hi")

    def test_send_message_not_member_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=False)

        svc = MessageService()
        with pytest.raises(MessageAccessDeniedException):
            svc.send_message(_user(), chat_id=1, text="Hi")

    def test_send_message_reader_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.membership_repository.get_role", return_value="reader")

        svc = MessageService()
        with pytest.raises(ReaderCannotSendMessageException):
            svc.send_message(_user(), chat_id=1, text="Hi")

    def test_send_message_locked_chat_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat(is_locked=True))
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.membership_repository.get_role", return_value="editor")

        svc = MessageService()
        with pytest.raises(ChatLockedException):
            svc.send_message(_user(), chat_id=1, text="Hi")


class TestMessageServiceGetMessages:

    def test_get_messages_happy_path(self, mocker):
        qs = MagicMock()
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.message_repository.get_messages_by_chat", return_value=qs)

        svc = MessageService()
        result = svc.get_messages(_user(), chat_id=1)

        assert result is qs

    def test_get_messages_access_denied_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=False)

        svc = MessageService()
        with pytest.raises(MessageAccessDeniedException):
            svc.get_messages(_user(), chat_id=1)

    def test_get_messages_chat_not_found_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=None)
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)

        svc = MessageService()
        with pytest.raises(ChatNotFoundException):
            svc.get_messages(_user(), chat_id=99)


class TestMessageServiceGetMessagesAdmin:

    def test_get_messages_admin_happy_path(self, mocker):
        qs = MagicMock()
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.message_repository.get_messages_by_chat", return_value=qs)

        svc = MessageService()
        result = svc.get_messages_admin(_user(), chat_id=1)

        assert result is qs

    def test_get_messages_admin_chat_not_found_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=None)

        svc = MessageService()
        with pytest.raises(ChatNotFoundException):
            svc.get_messages_admin(_user(), chat_id=99)


class TestMessageServiceClearHistory:

    def test_clear_history_owner_succeeds(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.membership_repository.is_chat_owner", return_value=True)
        soft_delete = mocker.patch(f"{MSG_SVC}.message_repository.soft_delete_by_chat")

        svc = MessageService()
        svc.clear_history(_user(), chat_id=1)

        soft_delete.assert_called_once_with(1, deleted_by=1)

    def test_clear_history_non_owner_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.membership_repository.is_chat_owner", return_value=False)

        svc = MessageService()
        with pytest.raises(NotChatOwnerException):
            svc.clear_history(_user(user_id=2), chat_id=1)

    def test_clear_history_not_member_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=False)

        svc = MessageService()
        with pytest.raises(MessageAccessDeniedException):
            svc.clear_history(_user(user_id=99), chat_id=1)

    def test_clear_history_chat_not_found_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=None)

        svc = MessageService()
        with pytest.raises(ChatNotFoundException):
            svc.clear_history(_user(), chat_id=99)


class TestMessageServiceDeleteMessage:

    def test_delete_message_owner_succeeds(self, mocker):
        msg = _msg()
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.message_repository.get_by_id_and_chat", return_value=msg)
        mocker.patch(f"{MSG_SVC}.membership_repository.is_chat_owner", return_value=True)

        svc = MessageService()
        svc.delete_message(_user(), chat_id=1, message_id=1)

        msg.delete.assert_called_once_with(deleted_by=1)

    def test_delete_message_non_owner_raises(self, mocker):
        msg = _msg()
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.message_repository.get_by_id_and_chat", return_value=msg)
        mocker.patch(f"{MSG_SVC}.membership_repository.is_chat_owner", return_value=False)

        svc = MessageService()
        with pytest.raises(MessageDeleteForbiddenException):
            svc.delete_message(_user(user_id=2), chat_id=1, message_id=1)

    def test_delete_message_author_non_owner_raises(self, mocker):
        """Message author without owner role cannot delete — owner-only rule."""
        user = _user(user_id=5)
        msg = _msg(created_by=5)
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.message_repository.get_by_id_and_chat", return_value=msg)
        mocker.patch(f"{MSG_SVC}.membership_repository.is_chat_owner", return_value=False)

        svc = MessageService()
        with pytest.raises(MessageDeleteForbiddenException):
            svc.delete_message(user, chat_id=1, message_id=1)

    def test_delete_message_not_found_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.message_repository.get_by_id_and_chat", return_value=None)

        svc = MessageService()
        with pytest.raises(MessageNotFoundException):
            svc.delete_message(_user(), chat_id=1, message_id=999)

    def test_delete_message_not_member_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=False)

        svc = MessageService()
        with pytest.raises(MessageAccessDeniedException):
            svc.delete_message(_user(user_id=99), chat_id=1, message_id=1)


class TestMessageServiceDeleteLastAiMessage:

    def test_delete_last_ai_message_happy_path(self, mocker):
        ai_msg = _msg(sender_type="system")
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.message_repository.get_last_ai_message", return_value=ai_msg)

        svc = MessageService()
        svc.delete_last_ai_message(_user(), chat_id=1)

        ai_msg.delete.assert_called_once_with(deleted_by=1)

    def test_delete_last_ai_message_none_raises(self, mocker):
        mocker.patch(f"{MSG_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{MSG_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{MSG_SVC}.message_repository.get_last_ai_message", return_value=None)

        svc = MessageService()
        with pytest.raises(NoMessageToRegenerateException):
            svc.delete_last_ai_message(_user(), chat_id=1)


# ===========================================================================
# PinnedMessageService
# ===========================================================================

class TestPinnedMessageService:

    def test_list_pinned_happy_path(self, mocker):
        pin = make_pin()
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{PIN_SVC}.pinned_message_repository.list_by_chat", return_value=[pin])

        svc = PinnedMessageService()
        result = svc.list_pinned(_user(), chat_id=1)

        assert result == [pin]

    def test_list_pinned_not_member_raises(self, mocker):
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=False)

        svc = PinnedMessageService()
        with pytest.raises(MessageAccessDeniedException):
            svc.list_pinned(_user(), chat_id=1)

    def test_pin_message_owner_succeeds(self, mocker):
        pin = make_pin()
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{PIN_SVC}.membership_repository.is_chat_owner", return_value=True)
        mocker.patch(f"{PIN_SVC}.message_repository.get_by_id_and_chat", return_value=_msg())
        mocker.patch(f"{PIN_SVC}.pinned_message_repository.pin", return_value=(pin, True))

        svc = PinnedMessageService()
        result = svc.pin_message(_user(), chat_id=1, message_id=1)

        assert result is pin

    def test_pin_message_not_member_raises(self, mocker):
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=False)

        svc = PinnedMessageService()
        with pytest.raises(MessageAccessDeniedException):
            svc.pin_message(_user(), chat_id=1, message_id=1)

    def test_pin_message_member_not_owner_raises(self, mocker):
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{PIN_SVC}.membership_repository.is_chat_owner", return_value=False)

        svc = PinnedMessageService()
        with pytest.raises(NotChatOwnerException):
            svc.pin_message(_user(user_id=2), chat_id=1, message_id=1)

    def test_pin_message_not_found_raises(self, mocker):
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{PIN_SVC}.membership_repository.is_chat_owner", return_value=True)
        mocker.patch(f"{PIN_SVC}.message_repository.get_by_id_and_chat", return_value=None)

        svc = PinnedMessageService()
        with pytest.raises(MessageNotFoundException):
            svc.pin_message(_user(), chat_id=1, message_id=999)

    def test_unpin_message_owner_succeeds(self, mocker):
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{PIN_SVC}.membership_repository.is_chat_owner", return_value=True)
        unpin = mocker.patch(f"{PIN_SVC}.pinned_message_repository.unpin")

        svc = PinnedMessageService()
        svc.unpin_message(_user(), chat_id=1, message_id=1)

        unpin.assert_called_once_with(1, 1)

    def test_unpin_message_not_member_raises(self, mocker):
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=False)

        svc = PinnedMessageService()
        with pytest.raises(MessageAccessDeniedException):
            svc.unpin_message(_user(), chat_id=1, message_id=1)

    def test_unpin_message_member_not_owner_raises(self, mocker):
        mocker.patch(f"{PIN_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{PIN_SVC}.membership_repository.is_chat_owner", return_value=False)

        svc = PinnedMessageService()
        with pytest.raises(NotChatOwnerException):
            svc.unpin_message(_user(user_id=2), chat_id=1, message_id=1)


# ===========================================================================
# BookmarkService
# ===========================================================================

class TestBookmarkService:

    def test_bookmark_happy_path(self, mocker):
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{BKM_SVC}.message_repository.get_by_id_and_chat", return_value=_msg())
        create = mocker.patch(f"{BKM_SVC}.bookmark_repository.create")

        svc = BookmarkService()
        svc.bookmark(_user(), chat_id=1, message_id=1)

        create.assert_called_once_with(message_id=1, user_id=1)

    def test_bookmark_not_member_raises(self, mocker):
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=False)

        svc = BookmarkService()
        with pytest.raises(MessageAccessDeniedException):
            svc.bookmark(_user(), chat_id=1, message_id=1)

    def test_bookmark_message_not_found_raises(self, mocker):
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{BKM_SVC}.message_repository.get_by_id_and_chat", return_value=None)

        svc = BookmarkService()
        with pytest.raises(MessageNotFoundException):
            svc.bookmark(_user(), chat_id=1, message_id=999)

    def test_unbookmark_happy_path(self, mocker):
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{BKM_SVC}.message_repository.get_by_id_and_chat", return_value=_msg())
        delete = mocker.patch(f"{BKM_SVC}.bookmark_repository.delete")

        svc = BookmarkService()
        svc.unbookmark(_user(), chat_id=1, message_id=1)

        delete.assert_called_once_with(message_id=1, user_id=1)

    def test_unbookmark_not_member_raises(self, mocker):
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=False)

        svc = BookmarkService()
        with pytest.raises(MessageAccessDeniedException):
            svc.unbookmark(_user(), chat_id=1, message_id=1)

    def test_unbookmark_message_not_found_raises(self, mocker):
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{BKM_SVC}.message_repository.get_by_id_and_chat", return_value=None)

        svc = BookmarkService()
        with pytest.raises(MessageNotFoundException):
            svc.unbookmark(_user(), chat_id=1, message_id=999)

    def test_list_bookmarked_happy_path(self, mocker):
        qs = MagicMock()
        qs.filter.return_value = qs
        mocker.patch(f"{BKM_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{BKM_SVC}.bookmark_repository.get_bookmarked_message_ids", return_value=[1, 2])
        mocker.patch(f"{BKM_SVC}.message_repository.get_messages_by_chat", return_value=qs)

        svc = BookmarkService()
        result = svc.list_bookmarked(_user(), chat_id=1)

        assert result is qs.filter.return_value

    def test_list_bookmarked_chat_not_found_raises(self, mocker):
        mocker.patch(f"{BKM_SVC}.chat_repository.get_by_id", return_value=None)

        svc = BookmarkService()
        with pytest.raises(ChatNotFoundException):
            svc.list_bookmarked(_user(), chat_id=99)

    def test_list_bookmarked_not_member_raises(self, mocker):
        mocker.patch(f"{BKM_SVC}.chat_repository.get_by_id", return_value=_chat())
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=False)

        svc = BookmarkService()
        with pytest.raises(MessageAccessDeniedException):
            svc.list_bookmarked(_user(), chat_id=1)

    def test_bookmark_is_personal_uses_caller_user_id(self, mocker):
        """Bookmarks always stored under the authenticated user's id, never another user's."""
        mocker.patch(f"{BKM_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{BKM_SVC}.message_repository.get_by_id_and_chat", return_value=_msg())
        create = mocker.patch(f"{BKM_SVC}.bookmark_repository.create")

        user = _user(user_id=42)
        svc = BookmarkService()
        svc.bookmark(user, chat_id=1, message_id=1)

        create.assert_called_once_with(message_id=1, user_id=42)


# ===========================================================================
# FeedbackService
# ===========================================================================

class TestFeedbackService:

    def test_set_feedback_happy_path(self, mocker):
        fb = make_feedback(value=1)
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.message_repository.get_by_id_and_chat", return_value=_msg(sender_type="system"))
        mocker.patch(f"{FBK_SVC}.feedback_repository.set", return_value=fb)

        svc = FeedbackService()
        result = svc.set_feedback(_user(), chat_id=1, message_id=1, value=1)

        assert result.value == 1

    def test_set_feedback_not_member_raises(self, mocker):
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=False)

        svc = FeedbackService()
        with pytest.raises(MessageAccessDeniedException):
            svc.set_feedback(_user(), chat_id=1, message_id=1, value=1)

    def test_set_feedback_message_not_found_raises(self, mocker):
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.message_repository.get_by_id_and_chat", return_value=None)

        svc = FeedbackService()
        with pytest.raises(MessageNotFoundException):
            svc.set_feedback(_user(), chat_id=1, message_id=999, value=1)

    def test_set_feedback_not_ai_message_raises(self, mocker):
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.message_repository.get_by_id_and_chat", return_value=_msg(sender_type="user"))

        svc = FeedbackService()
        with pytest.raises(NotAIMessageException):
            svc.set_feedback(_user(), chat_id=1, message_id=1, value=1)

    def test_set_feedback_thumbs_down(self, mocker):
        fb = make_feedback(value=-1)
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.message_repository.get_by_id_and_chat", return_value=_msg(sender_type="system"))
        mocker.patch(f"{FBK_SVC}.feedback_repository.set", return_value=fb)

        svc = FeedbackService()
        result = svc.set_feedback(_user(), chat_id=1, message_id=1, value=-1)

        assert result.value == -1

    def test_set_feedback_is_personal_uses_caller_user_id(self, mocker):
        """Feedback is always stored under the authenticated user's id."""
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.message_repository.get_by_id_and_chat", return_value=_msg(sender_type="system"))
        repo_set = mocker.patch(f"{FBK_SVC}.feedback_repository.set", return_value=make_feedback(value=1))

        user = _user(user_id=77)
        svc = FeedbackService()
        svc.set_feedback(user, chat_id=1, message_id=1, value=1)

        repo_set.assert_called_once_with(message_id=1, user_id=77, value=1)

    def test_delete_feedback_happy_path(self, mocker):
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.message_repository.get_by_id_and_chat", return_value=_msg(sender_type="system"))
        repo_del = mocker.patch(f"{FBK_SVC}.feedback_repository.delete")

        svc = FeedbackService()
        svc.delete_feedback(_user(), chat_id=1, message_id=1)

        repo_del.assert_called_once_with(message_id=1, user_id=1)

    def test_delete_feedback_not_member_raises(self, mocker):
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=False)

        svc = FeedbackService()
        with pytest.raises(MessageAccessDeniedException):
            svc.delete_feedback(_user(), chat_id=1, message_id=1)

    def test_delete_feedback_message_not_found_raises(self, mocker):
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.message_repository.get_by_id_and_chat", return_value=None)

        svc = FeedbackService()
        with pytest.raises(MessageNotFoundException):
            svc.delete_feedback(_user(), chat_id=1, message_id=999)

    def test_delete_feedback_not_ai_message_raises(self, mocker):
        mocker.patch(f"{FBK_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{FBK_SVC}.message_repository.get_by_id_and_chat", return_value=_msg(sender_type="user"))

        svc = FeedbackService()
        with pytest.raises(NotAIMessageException):
            svc.delete_feedback(_user(), chat_id=1, message_id=1)


# ===========================================================================
# ThreadService
# ===========================================================================

class TestThreadService:

    def test_get_thread_happy_path(self, mocker):
        replies = [make_thread_reply(), make_thread_reply(reply_id=2)]
        mocker.patch(f"{THR_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{THR_SVC}.message_repository.get_by_id_and_chat", return_value=_msg())
        mocker.patch(f"{THR_SVC}.thread_repository.get_by_message", return_value=replies)

        svc = ThreadService()
        result = svc.get_thread(_user(), chat_id=1, message_id=1)

        assert result == replies

    def test_get_thread_not_member_raises(self, mocker):
        mocker.patch(f"{THR_SVC}.membership_repository.is_active_member", return_value=False)

        svc = ThreadService()
        with pytest.raises(MessageAccessDeniedException):
            svc.get_thread(_user(), chat_id=1, message_id=1)

    def test_get_thread_message_not_found_raises(self, mocker):
        mocker.patch(f"{THR_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{THR_SVC}.message_repository.get_by_id_and_chat", return_value=None)

        svc = ThreadService()
        with pytest.raises(MessageNotFoundException):
            svc.get_thread(_user(), chat_id=1, message_id=999)

    def test_add_reply_happy_path(self, mocker):
        reply = make_thread_reply()
        mocker.patch(f"{THR_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{THR_SVC}.message_repository.get_by_id_and_chat", return_value=_msg())
        mocker.patch(f"{THR_SVC}.thread_repository.create", return_value=reply)

        svc = ThreadService()
        result = svc.add_reply(_user(), chat_id=1, message_id=1, message_text="A reply")

        assert result is reply

    def test_add_reply_passes_correct_args(self, mocker):
        reply = make_thread_reply()
        mocker.patch(f"{THR_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{THR_SVC}.message_repository.get_by_id_and_chat", return_value=_msg())
        create = mocker.patch(f"{THR_SVC}.thread_repository.create", return_value=reply)

        user = _user(user_id=5)
        svc = ThreadService()
        svc.add_reply(user, chat_id=1, message_id=1, message_text="My reply")

        create.assert_called_once_with(
            parent_message_id=1,
            message="My reply",
            created_by=5,
        )

    def test_add_reply_not_member_raises(self, mocker):
        mocker.patch(f"{THR_SVC}.membership_repository.is_active_member", return_value=False)

        svc = ThreadService()
        with pytest.raises(MessageAccessDeniedException):
            svc.add_reply(_user(), chat_id=1, message_id=1, message_text="Reply")

    def test_add_reply_message_not_found_raises(self, mocker):
        mocker.patch(f"{THR_SVC}.membership_repository.is_active_member", return_value=True)
        mocker.patch(f"{THR_SVC}.message_repository.get_by_id_and_chat", return_value=None)

        svc = ThreadService()
        with pytest.raises(MessageNotFoundException):
            svc.add_reply(_user(), chat_id=1, message_id=999, message_text="Reply")
