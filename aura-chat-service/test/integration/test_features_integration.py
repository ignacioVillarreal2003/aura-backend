"""
Integration tests for bookmarks, pinned messages, feedback, threads, and share links.
"""
import pytest
from django.utils import timezone

from apps.chat.exceptions import (
    ChatAccessDeniedException,
    ShareLinkExpiredOrInactiveException,
    ShareLinkNotFoundException,
)
from apps.chat.models.chat_share_link import ChatShareLink
from apps.chat.services.chat_service import chat_service
from apps.chat.services.share_link_service import share_link_service
from apps.message.models.chat_message import ChatMessage  # backward-compat alias → ArtifactMessage
from apps.message.repositories.message_repository import message_repository
from apps.message.exceptions import MessageAccessDeniedException, MessageNotFoundException, NotAIMessageException
from apps.message.models.message_bookmark import ArtifactBookmark
from apps.message.models.message_feedback import ArtifactFeedback
from apps.message.models.message_thread_reply import ArtifactThreadReply
from apps.message.models.pinned_message import ArtifactPin
from apps.message.services.bookmark_service import bookmark_service
from apps.message.services.feedback_service import feedback_service
from apps.message.services.pinned_message_service import pinned_message_service
from apps.message.services.thread_service import thread_service
from apps.membership.services.membership_service import membership_service

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------

def test_bookmark_creates_record(owner, chat, user_message):
    bookmark_service.bookmark(owner, chat.id, user_message.artifact_id)
    assert ArtifactBookmark.objects.filter(artifact_id=user_message.artifact_id, user_id=owner.id).exists()


def test_bookmark_same_message_twice_is_idempotent(owner, chat, user_message):
    bookmark_service.bookmark(owner, chat.id, user_message.artifact_id)
    bookmark_service.bookmark(owner, chat.id, user_message.artifact_id)
    assert ArtifactBookmark.objects.filter(artifact_id=user_message.artifact_id, user_id=owner.id).count() == 1


def test_unbookmark_removes_record(owner, chat, user_message):
    bookmark_service.bookmark(owner, chat.id, user_message.artifact_id)
    bookmark_service.unbookmark(owner, chat.id, user_message.artifact_id)
    assert not ArtifactBookmark.objects.filter(artifact_id=user_message.artifact_id, user_id=owner.id).exists()


def test_list_bookmarked_returns_bookmarked_messages(owner, chat, user_message, ai_message):
    bookmark_service.bookmark(owner, chat.id, user_message.artifact_id)
    results = list(bookmark_service.list_bookmarked(owner, chat.id))
    artifact_ids = [m.artifact_id for m in results]
    assert user_message.artifact_id in artifact_ids
    assert ai_message.artifact_id not in artifact_ids


def test_bookmark_non_member_raises(chat, other_user, user_message):
    with pytest.raises(MessageAccessDeniedException):
        bookmark_service.bookmark(other_user, chat.id, user_message.artifact_id)


def test_bookmark_unknown_message_raises(owner, chat):
    with pytest.raises(MessageNotFoundException):
        bookmark_service.bookmark(owner, chat.id, 999999)


# ---------------------------------------------------------------------------
# Pinned Messages
# ---------------------------------------------------------------------------

def test_pin_message_creates_record(owner, chat, user_message):
    pin = pinned_message_service.pin_message(owner, chat.id, user_message.artifact_id)
    assert ArtifactPin.objects.filter(artifact_id=user_message.artifact_id, chat_id=chat.id).exists()
    assert pin.pinned_by == owner.id


def test_pin_same_message_twice_is_idempotent(owner, chat, user_message):
    pinned_message_service.pin_message(owner, chat.id, user_message.artifact_id)
    pinned_message_service.pin_message(owner, chat.id, user_message.artifact_id)
    assert ArtifactPin.objects.filter(artifact_id=user_message.artifact_id, chat_id=chat.id).count() == 1


def test_unpin_message_removes_record(owner, chat, user_message):
    pinned_message_service.pin_message(owner, chat.id, user_message.artifact_id)
    pinned_message_service.unpin_message(owner, chat.id, user_message.artifact_id)
    assert not ArtifactPin.objects.filter(artifact_id=user_message.artifact_id, chat_id=chat.id).exists()


def test_list_pinned_returns_pinned_messages(owner, chat, user_message, ai_message):
    pinned_message_service.pin_message(owner, chat.id, user_message.artifact_id)
    results = list(pinned_message_service.list_pinned(owner, chat.id))
    artifact_ids = [p.artifact_id for p in results]
    assert user_message.artifact_id in artifact_ids
    assert ai_message.artifact_id not in artifact_ids


def test_pin_non_member_raises(chat, other_user, user_message):
    with pytest.raises(MessageAccessDeniedException):
        pinned_message_service.pin_message(other_user, chat.id, user_message.artifact_id)


def test_pin_unknown_message_raises(owner, chat):
    with pytest.raises(MessageNotFoundException):
        pinned_message_service.pin_message(owner, chat.id, 999999)


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

def test_set_feedback_thumbs_up_persists(owner, chat, ai_message):
    feedback_service.set_feedback(owner, chat.id, ai_message.artifact_id, value=1)
    fb = ArtifactFeedback.objects.get(artifact_id=ai_message.artifact_id, user_id=owner.id)
    assert fb.value == ArtifactFeedback.Value.THUMBS_UP


def test_set_feedback_thumbs_down_persists(owner, chat, ai_message):
    feedback_service.set_feedback(owner, chat.id, ai_message.artifact_id, value=-1)
    fb = ArtifactFeedback.objects.get(artifact_id=ai_message.artifact_id, user_id=owner.id)
    assert fb.value == ArtifactFeedback.Value.THUMBS_DOWN


def test_set_feedback_updates_existing(owner, chat, ai_message):
    feedback_service.set_feedback(owner, chat.id, ai_message.artifact_id, value=1)
    feedback_service.set_feedback(owner, chat.id, ai_message.artifact_id, value=-1)
    assert ArtifactFeedback.objects.filter(artifact_id=ai_message.artifact_id, user_id=owner.id).count() == 1
    fb = ArtifactFeedback.objects.get(artifact_id=ai_message.artifact_id, user_id=owner.id)
    assert fb.value == -1


def test_delete_feedback_removes_record(owner, chat, ai_message):
    feedback_service.set_feedback(owner, chat.id, ai_message.artifact_id, value=1)
    feedback_service.delete_feedback(owner, chat.id, ai_message.artifact_id)
    assert not ArtifactFeedback.objects.filter(artifact_id=ai_message.artifact_id, user_id=owner.id).exists()


def test_feedback_on_user_message_raises(owner, chat, user_message):
    with pytest.raises(NotAIMessageException):
        feedback_service.set_feedback(owner, chat.id, user_message.artifact_id, value=1)


def test_feedback_non_member_raises(chat, other_user, ai_message):
    with pytest.raises(MessageAccessDeniedException):
        feedback_service.set_feedback(other_user, chat.id, ai_message.artifact_id, value=1)


# ---------------------------------------------------------------------------
# Thread replies
# ---------------------------------------------------------------------------

def test_add_reply_persists_to_db(owner, chat, user_message):
    reply = thread_service.add_reply(owner, chat.id, user_message.artifact_id, message_text="My reply")
    assert ArtifactThreadReply.objects.filter(
        parent_artifact_id=user_message.artifact_id, created_by=owner.id
    ).exists()
    assert reply.message == "My reply"


def test_get_thread_returns_replies_in_order(owner, chat, user_message):
    thread_service.add_reply(owner, chat.id, user_message.artifact_id, message_text="First")
    thread_service.add_reply(owner, chat.id, user_message.artifact_id, message_text="Second")
    replies = list(thread_service.get_thread(owner, chat.id, user_message.artifact_id))
    assert len(replies) == 2
    assert replies[0].message == "First"
    assert replies[1].message == "Second"


def test_add_reply_non_member_raises(chat, other_user, user_message):
    with pytest.raises(MessageAccessDeniedException):
        thread_service.add_reply(other_user, chat.id, user_message.artifact_id, message_text="Hack")


def test_add_reply_unknown_message_raises(owner, chat):
    with pytest.raises(MessageNotFoundException):
        thread_service.add_reply(owner, chat.id, 999999, message_text="Ghost")


# ---------------------------------------------------------------------------
# Share links
# ---------------------------------------------------------------------------

def test_create_share_link_persists(owner, chat):
    link = share_link_service.create_link(owner, chat.id)
    assert ChatShareLink.objects.filter(id=link.id, chat_id=chat.id, is_active=True).exists()


def test_create_share_link_non_owner_raises(chat, other_user):
    with pytest.raises(ChatAccessDeniedException):
        share_link_service.create_link(other_user, chat.id)


def test_revoke_share_link_deactivates_it(owner, chat):
    link = share_link_service.create_link(owner, chat.id)
    share_link_service.revoke_link(owner, chat.id, link.id)
    link.refresh_from_db()
    assert link.is_active is False


def test_get_public_messages_via_active_link(owner, chat, user_message):
    link = share_link_service.create_link(owner, chat.id)
    messages = list(share_link_service.get_public_messages(link.token))
    assert user_message.id in [m.id for m in messages]


def test_get_public_messages_via_revoked_link_raises(owner, chat):
    link = share_link_service.create_link(owner, chat.id)
    share_link_service.revoke_link(owner, chat.id, link.id)
    with pytest.raises(ShareLinkExpiredOrInactiveException):
        share_link_service.get_public_messages(link.token)


def test_get_public_messages_via_expired_link_raises(owner, chat):
    past = timezone.now() - timezone.timedelta(hours=1)
    link = share_link_service.create_link(owner, chat.id, expires_at=past)
    with pytest.raises(ShareLinkExpiredOrInactiveException):
        share_link_service.get_public_messages(link.token)


def test_create_share_link_persists_expires_at(owner, chat):
    future = timezone.now() + timezone.timedelta(days=7)
    link = share_link_service.create_link(owner, chat.id, expires_at=future)
    link.refresh_from_db()
    assert link.expires_at is not None


def test_get_public_messages_via_future_expiry_link_works(owner, chat, user_message):
    future = timezone.now() + timezone.timedelta(hours=1)
    link = share_link_service.create_link(owner, chat.id, expires_at=future)
    messages = list(share_link_service.get_public_messages(link.token))
    assert user_message.id in [m.id for m in messages]


def test_get_public_messages_only_returns_that_chats_messages(owner, chat, user_message):
    """A share link must only expose messages from its own chat, never another chat's."""
    other_chat = chat_service.create_chat(owner, name="Otro chat")
    other_msg = message_repository.create(
        chat_id=other_chat.id,
        message="Mensaje de otro chat",
        sender_type=ChatMessage.SenderType.USER,
        created_by=owner.id,
    )
    link = share_link_service.create_link(owner, chat.id)
    ids = [m.id for m in share_link_service.get_public_messages(link.token)]
    assert user_message.id in ids
    assert other_msg.id not in ids


# ── list_links: active filter + ordering ─────────────────────────────────────

def test_list_share_links_returns_active_links(owner, chat):
    link1 = share_link_service.create_link(owner, chat.id)
    link2 = share_link_service.create_link(owner, chat.id)
    ids = [link.id for link in share_link_service.list_links(owner, chat.id)]
    assert link1.id in ids
    assert link2.id in ids


def test_list_share_links_active_only_excludes_revoked(owner, chat):
    active = share_link_service.create_link(owner, chat.id)
    revoked = share_link_service.create_link(owner, chat.id)
    share_link_service.revoke_link(owner, chat.id, revoked.id)
    ids = [link.id for link in share_link_service.list_links(owner, chat.id)]
    assert active.id in ids
    assert revoked.id not in ids


def test_list_share_links_active_false_includes_revoked(owner, chat):
    active = share_link_service.create_link(owner, chat.id)
    revoked = share_link_service.create_link(owner, chat.id)
    share_link_service.revoke_link(owner, chat.id, revoked.id)
    ids = [link.id for link in share_link_service.list_links(owner, chat.id, active_only=False)]
    assert active.id in ids
    assert revoked.id in ids


def test_list_share_links_ordered_by_created_at_desc(owner, chat):
    first = share_link_service.create_link(owner, chat.id)
    second = share_link_service.create_link(owner, chat.id)
    ids = [link.id for link in share_link_service.list_links(owner, chat.id)]
    # newest first
    assert ids.index(second.id) < ids.index(first.id)


def test_list_share_links_non_owner_raises(chat, other_user):
    with pytest.raises(ChatAccessDeniedException):
        share_link_service.list_links(other_user, chat.id)


# ── revoke: cross-chat isolation ─────────────────────────────────────────────

def test_revoke_share_link_wrong_chat_raises_not_found(owner, chat):
    """A link belongs to one chat; revoking it via a different chat_id must 404,
    not silently deactivate it (prevents cross-chat tampering)."""
    other_chat = chat_service.create_chat(owner, name="Otro chat")
    link = share_link_service.create_link(owner, chat.id)
    with pytest.raises(ShareLinkNotFoundException):
        share_link_service.revoke_link(owner, other_chat.id, link.id)
    link.refresh_from_db()
    assert link.is_active is True  # untouched


def test_revoke_share_link_unknown_link_raises_not_found(owner, chat):
    with pytest.raises(ShareLinkNotFoundException):
        share_link_service.revoke_link(owner, chat.id, 999999)


def test_revoke_share_link_non_owner_raises(owner, chat, other_user):
    link = share_link_service.create_link(owner, chat.id)
    with pytest.raises(ChatAccessDeniedException):
        share_link_service.revoke_link(other_user, chat.id, link.id)
    link.refresh_from_db()
    assert link.is_active is True
