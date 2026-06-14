import uuid
import pytest
from django.utils import timezone

from apps.chat.exceptions import (
    ChatAccessDeniedException,
    ChatNotFoundException,
    ShareLinkExpiredOrInactiveException,
    ShareLinkNotFoundException,
)
from apps.chat.services.share_link_service import ShareLinkService
from test.conftest import make_chat, make_share_link, make_user

SVC = "apps.chat.services.share_link_service"

service = ShareLinkService()


def _patch_perms(mocker):
    mocker.patch(f"{SVC}.AccessControl.require_permissions")


def _patch_chat(mocker, chat):
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=chat)


def _patch_not_owner(mocker):
    """Owner/creator gate now also consults membership; deny the membership path."""
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)


def _ordered_qs(mocker, messages):
    """get_public_messages applies .order_by('created_at') on the repo result;
    return a queryset-like whose order_by yields the given messages."""
    qs = mocker.MagicMock()
    qs.order_by.return_value = messages
    return qs


# ══════════════════════════════════════════════════════════════════════════════
# create_link
# ══════════════════════════════════════════════════════════════════════════════

def test_create_link_owner_succeeds(mocker):
    """Chat creator can create a share link."""
    user = make_user(user_id=1)
    chat = make_chat(chat_id=10, created_by=1)
    link = make_share_link(link_id=1, chat_id=10, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.share_link_repository.create", return_value=link)
    result = service.create_link(user, chat_id=10)
    assert result is link


def test_create_link_passes_expires_at_to_repo(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=10, created_by=1)
    link = make_share_link()
    future = timezone.now().replace(year=2099)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    create = mocker.patch(f"{SVC}.share_link_repository.create", return_value=link)
    service.create_link(user, chat_id=10, expires_at=future)
    _, kwargs = create.call_args
    assert kwargs["expires_at"] == future


def test_create_link_non_creator_raises_403(mocker):
    """Only the chat creator can create share links — any other user is denied."""
    user = make_user(user_id=2)
    chat = make_chat(chat_id=10, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_not_owner(mocker)
    with pytest.raises(ChatAccessDeniedException):
        service.create_link(user, chat_id=10)


def test_create_link_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=None)
    with pytest.raises(ChatNotFoundException):
        service.create_link(user, chat_id=999)


def test_create_link_without_expires_at(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=10, created_by=1)
    link = make_share_link(expires_at=None)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    create = mocker.patch(f"{SVC}.share_link_repository.create", return_value=link)
    service.create_link(user, chat_id=10)
    _, kwargs = create.call_args
    assert kwargs["expires_at"] is None


# ══════════════════════════════════════════════════════════════════════════════
# list_links
# ══════════════════════════════════════════════════════════════════════════════

def test_list_links_owner_returns_active_links_by_default(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=10, created_by=1)
    links = [make_share_link(link_id=1), make_share_link(link_id=2)]
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    repo = mocker.patch(f"{SVC}.share_link_repository.list_by_chat", return_value=links)
    result = service.list_links(user, chat_id=10)
    assert result is links
    repo.assert_called_once_with(10, active_only=True)


def test_list_links_active_only_false_passes_to_repo(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=10, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    repo = mocker.patch(f"{SVC}.share_link_repository.list_by_chat", return_value=[])
    service.list_links(user, chat_id=10, active_only=False)
    repo.assert_called_once_with(10, active_only=False)


def test_list_links_non_creator_raises_403(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=10, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_not_owner(mocker)
    with pytest.raises(ChatAccessDeniedException):
        service.list_links(user, chat_id=10)


def test_list_links_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=None)
    with pytest.raises(ChatNotFoundException):
        service.list_links(user, chat_id=999)


def test_list_links_empty_chat_returns_empty_list(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=10, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.share_link_repository.list_by_chat", return_value=[])
    result = service.list_links(user, chat_id=10)
    assert list(result) == []


# ══════════════════════════════════════════════════════════════════════════════
# revoke_link
# ══════════════════════════════════════════════════════════════════════════════

def test_revoke_link_owner_succeeds(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=10, created_by=1)
    link = make_share_link(link_id=5, chat_id=10, is_active=True)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.share_link_repository.get_by_id", return_value=link)
    deactivate = mocker.patch(f"{SVC}.share_link_repository.deactivate")
    service.revoke_link(user, chat_id=10, link_id=5)
    deactivate.assert_called_once_with(link)


def test_revoke_link_non_creator_raises_403(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=10, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_not_owner(mocker)
    with pytest.raises(ChatAccessDeniedException):
        service.revoke_link(user, chat_id=10, link_id=5)


def test_revoke_link_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=None)
    with pytest.raises(ChatNotFoundException):
        service.revoke_link(user, chat_id=999, link_id=5)


def test_revoke_link_link_not_found_raises_404(mocker):
    """Link doesn't exist for the given chat_id and link_id."""
    user = make_user(user_id=1)
    chat = make_chat(chat_id=10, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.share_link_repository.get_by_id", return_value=None)
    with pytest.raises(ShareLinkNotFoundException):
        service.revoke_link(user, chat_id=10, link_id=999)


def test_revoke_link_calls_repo_with_correct_ids(mocker):
    """Repo is called with the exact link_id and chat_id to prevent cross-chat access."""
    user = make_user(user_id=1)
    chat = make_chat(chat_id=10, created_by=1)
    link = make_share_link(link_id=5, chat_id=10)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    get_by_id = mocker.patch(f"{SVC}.share_link_repository.get_by_id", return_value=link)
    mocker.patch(f"{SVC}.share_link_repository.deactivate")
    service.revoke_link(user, chat_id=10, link_id=5)
    get_by_id.assert_called_once_with(5, 10)


def test_revoke_link_already_inactive_still_deactivates(mocker):
    """Revoking an already-inactive link should not raise — repo handles idempotency."""
    user = make_user(user_id=1)
    chat = make_chat(chat_id=10, created_by=1)
    link = make_share_link(link_id=5, chat_id=10, is_active=False)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.share_link_repository.get_by_id", return_value=link)
    deactivate = mocker.patch(f"{SVC}.share_link_repository.deactivate")
    service.revoke_link(user, chat_id=10, link_id=5)
    deactivate.assert_called_once_with(link)


# ══════════════════════════════════════════════════════════════════════════════
# get_public_messages — no authentication required
# ══════════════════════════════════════════════════════════════════════════════

def test_get_public_messages_valid_active_link_returns_messages(mocker):
    token = uuid.uuid4()
    link = make_share_link(is_active=True, expires_at=None)
    messages = [object(), object()]
    mocker.patch(f"{SVC}.share_link_repository.get_by_token", return_value=link)
    mocker.patch(f"{SVC}.message_repository.get_messages_by_chat", return_value=_ordered_qs(mocker, messages))
    result = service.get_public_messages(token)
    assert result is messages


def test_get_public_messages_token_not_found_raises_404(mocker):
    token = uuid.uuid4()
    mocker.patch(f"{SVC}.share_link_repository.get_by_token", return_value=None)
    with pytest.raises(ShareLinkNotFoundException):
        service.get_public_messages(token)


def test_get_public_messages_inactive_link_raises_400(mocker):
    token = uuid.uuid4()
    link = make_share_link(is_active=False)
    mocker.patch(f"{SVC}.share_link_repository.get_by_token", return_value=link)
    with pytest.raises(ShareLinkExpiredOrInactiveException):
        service.get_public_messages(token)


def test_get_public_messages_expired_link_raises_400(mocker):
    token = uuid.uuid4()
    past = timezone.now().replace(year=2000)
    link = make_share_link(is_active=True, expires_at=past)
    mocker.patch(f"{SVC}.share_link_repository.get_by_token", return_value=link)
    with pytest.raises(ShareLinkExpiredOrInactiveException):
        service.get_public_messages(token)


def test_get_public_messages_future_expiry_is_valid(mocker):
    """A link with a future expiry must be treated as valid."""
    token = uuid.uuid4()
    future = timezone.now().replace(year=2099)
    link = make_share_link(is_active=True, expires_at=future)
    messages = []
    mocker.patch(f"{SVC}.share_link_repository.get_by_token", return_value=link)
    mocker.patch(f"{SVC}.message_repository.get_messages_by_chat", return_value=_ordered_qs(mocker, messages))
    result = service.get_public_messages(token)
    assert result is messages


def test_get_public_messages_no_expiry_is_valid(mocker):
    """A link with no expires_at must never expire."""
    token = uuid.uuid4()
    link = make_share_link(is_active=True, expires_at=None)
    mocker.patch(f"{SVC}.share_link_repository.get_by_token", return_value=link)
    messages = []
    mocker.patch(f"{SVC}.message_repository.get_messages_by_chat", return_value=_ordered_qs(mocker, messages))
    result = service.get_public_messages(token)
    assert result is messages


def test_get_public_messages_inactive_takes_precedence_over_expiry(mocker):
    """An inactive link raises even if it hasn't expired yet."""
    token = uuid.uuid4()
    future = timezone.now().replace(year=2099)
    link = make_share_link(is_active=False, expires_at=future)
    mocker.patch(f"{SVC}.share_link_repository.get_by_token", return_value=link)
    with pytest.raises(ShareLinkExpiredOrInactiveException):
        service.get_public_messages(token)


def test_get_public_messages_queries_correct_chat(mocker):
    token = uuid.uuid4()
    link = make_share_link(link_id=1, chat_id=42, is_active=True, expires_at=None)
    mocker.patch(f"{SVC}.share_link_repository.get_by_token", return_value=link)
    get_messages = mocker.patch(
        f"{SVC}.message_repository.get_messages_by_chat", return_value=_ordered_qs(mocker, [])
    )
    service.get_public_messages(token)
    get_messages.assert_called_once_with(42)
