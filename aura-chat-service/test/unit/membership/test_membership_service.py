import pytest
from django.db import IntegrityError

from apps.chat.exceptions import ChatNotFoundException
from apps.membership.exceptions import (
    CannotRemoveOwnerException,
    MembershipAlreadyExistsException,
    MembershipForbiddenException,
    MembershipNotFoundException,
    RoleUpdateForbiddenException,
)
from apps.membership.services.membership_service import MembershipService
from core.exceptions import ValidationException
from test.conftest import make_chat, make_membership, make_user

SVC = "apps.membership.services.membership_service"

service = MembershipService()


def _patch_perms(mocker):
    mocker.patch(f"{SVC}.AccessControl.require_permissions")


def _patch_chat(mocker, chat):
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=chat)


def _patch_chat_not_found(mocker):
    mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=None)


def _patch_atomic(mocker):
    """Make @transaction.atomic a no-op so transactional service methods run without a real DB."""
    mocker.patch("django.db.transaction.Atomic.__enter__", return_value=None)
    mocker.patch("django.db.transaction.Atomic.__exit__", return_value=False)
    mocker.patch(f"{SVC}.on_commit", side_effect=lambda fn: None)


def _patch_atomic_run_oncommit(mocker):
    """Like _patch_atomic but runs on_commit callbacks immediately so post-commit
    side effects (notifications, WS broadcasts) can be asserted."""
    mocker.patch("django.db.transaction.Atomic.__enter__", return_value=None)
    mocker.patch("django.db.transaction.Atomic.__exit__", return_value=False)
    mocker.patch(f"{SVC}.on_commit", side_effect=lambda fn: fn())


# ══════════════════════════════════════════════════════════════════════════════
# list_members
# ══════════════════════════════════════════════════════════════════════════════

def test_list_members_active_member_can_list(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=True)
    qs = object()
    mocker.patch(f"{SVC}.membership_repository.list_by_chat", return_value=qs)
    result = service.list_members(user, chat_id=1)
    assert result is qs


def test_list_members_owner_can_list(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=True)
    qs = object()
    mocker.patch(f"{SVC}.membership_repository.list_by_chat", return_value=qs)
    result = service.list_members(user, chat_id=1)
    assert result is qs


def test_list_members_non_member_raises_403(mocker):
    user = make_user(user_id=99)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=False)
    with pytest.raises(MembershipForbiddenException):
        service.list_members(user, chat_id=1)


def test_list_members_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    _patch_chat_not_found(mocker)
    with pytest.raises(ChatNotFoundException):
        service.list_members(user, chat_id=999)


def test_list_members_status_filter_forwarded(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=True)
    repo = mocker.patch(f"{SVC}.membership_repository.list_by_chat", return_value=[])
    service.list_members(user, chat_id=1, status="pending")
    repo.assert_called_once_with(1, status="pending")


def test_list_members_none_status_returns_all(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.is_active_member", return_value=True)
    repo = mocker.patch(f"{SVC}.membership_repository.list_by_chat", return_value=[])
    service.list_members(user, chat_id=1, status=None)
    repo.assert_called_once_with(1, status=None)


# ══════════════════════════════════════════════════════════════════════════════
# list_members_admin
# ══════════════════════════════════════════════════════════════════════════════

def test_list_members_admin_succeeds(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    qs = object()
    mocker.patch(f"{SVC}.membership_repository.list_by_chat", return_value=qs)
    result = service.list_members_admin(user, chat_id=1)
    assert result is qs


def test_list_members_admin_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    _patch_chat_not_found(mocker)
    with pytest.raises(ChatNotFoundException):
        service.list_members_admin(user, chat_id=999)


def test_list_members_admin_status_filter_forwarded(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    repo = mocker.patch(f"{SVC}.membership_repository.list_by_chat", return_value=[])
    service.list_members_admin(user, chat_id=1, status="active")
    repo.assert_called_once_with(1, status="active")


def test_list_members_admin_no_ownership_check(mocker):
    user = make_user(user_id=99)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    mocker.patch(f"{SVC}.membership_repository.list_by_chat", return_value=[])
    # Should not raise even though user is not the chat owner
    service.list_members_admin(user, chat_id=1)


# ══════════════════════════════════════════════════════════════════════════════
# list_my_memberships
# ══════════════════════════════════════════════════════════════════════════════

def test_list_my_memberships_returns_own_memberships(mocker):
    user = make_user(user_id=5)
    _patch_perms(mocker)
    repo = mocker.patch(f"{SVC}.membership_repository.list_by_member", return_value=[])
    service.list_my_memberships(user)
    repo.assert_called_once_with(member_id=5, status=None)


def test_list_my_memberships_status_forwarded(mocker):
    user = make_user(user_id=5)
    _patch_perms(mocker)
    repo = mocker.patch(f"{SVC}.membership_repository.list_by_member", return_value=[])
    service.list_my_memberships(user, status="pending")
    repo.assert_called_once_with(member_id=5, status="pending")


def test_list_my_memberships_always_uses_own_user_id(mocker):
    user = make_user(user_id=7)
    _patch_perms(mocker)
    repo = mocker.patch(f"{SVC}.membership_repository.list_by_member", return_value=[])
    service.list_my_memberships(user)
    _, kwargs = repo.call_args
    assert kwargs["member_id"] == 7


# ══════════════════════════════════════════════════════════════════════════════
# add_members
# ══════════════════════════════════════════════════════════════════════════════

def test_add_members_creator_can_invite(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    membership = make_membership(member_id=2, chat_id=1, status="pending")
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    mocker.patch(f"{SVC}.membership_repository.get_existing_member_ids_in", return_value=set())
    mocker.patch(f"{SVC}.membership_repository.create", return_value=membership)
    result = service.add_members(user, chat_id=1, member_ids=[2])
    assert len(result) == 1
    assert result[0].member_id == 2


def test_add_members_role_owner_can_invite(mocker):
    """A non-creator user with role=owner in the membership should be able to invite."""
    user = make_user(user_id=5)
    chat = make_chat(chat_id=1, created_by=1)
    membership = make_membership(member_id=2, chat_id=1, status="pending")
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=True)
    mocker.patch(f"{SVC}.membership_repository.get_existing_member_ids_in", return_value=set())
    mocker.patch(f"{SVC}.membership_repository.create", return_value=membership)
    result = service.add_members(user, chat_id=1, member_ids=[2])
    assert len(result) == 1


def test_add_members_regular_member_raises_403(mocker):
    """A user who is neither creator nor role=owner cannot invite."""
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    with pytest.raises(MembershipForbiddenException):
        service.add_members(user, chat_id=1, member_ids=[3])


def test_add_members_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    _patch_chat_not_found(mocker)
    _patch_atomic(mocker)
    with pytest.raises(ChatNotFoundException):
        service.add_members(user, chat_id=999, member_ids=[2])


def test_add_members_already_exists_raises_409(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    mocker.patch(f"{SVC}.membership_repository.get_existing_member_ids_in", return_value={2})
    with pytest.raises(MembershipAlreadyExistsException):
        service.add_members(user, chat_id=1, member_ids=[2])


def test_add_members_creates_pending_status(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    mocker.patch(f"{SVC}.membership_repository.get_existing_member_ids_in", return_value=set())
    create = mocker.patch(f"{SVC}.membership_repository.create", return_value=make_membership(status="pending"))
    service.add_members(user, chat_id=1, member_ids=[2])
    _, kwargs = create.call_args
    assert kwargs["status"] == "pending"


def test_add_members_multiple_ids_creates_all(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    mocker.patch(f"{SVC}.membership_repository.get_existing_member_ids_in", return_value=set())
    mocker.patch(f"{SVC}.membership_repository.create", side_effect=[
        make_membership(member_id=2),
        make_membership(member_id=3),
    ])
    result = service.add_members(user, chat_id=1, member_ids=[2, 3])
    assert len(result) == 2


# ══════════════════════════════════════════════════════════════════════════════
# update_member (status)
# ══════════════════════════════════════════════════════════════════════════════

def test_update_member_self_pending_to_active(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    membership = make_membership(member_id=2, chat_id=1, status="pending")
    updated = make_membership(member_id=2, chat_id=1, status="active")
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.get_by_chat_and_member_for_update", return_value=membership)
    mocker.patch(f"{SVC}.membership_repository.update_status", return_value=updated)
    result = service.update_member(user, chat_id=1, member_id=2, new_status="active")
    assert result.status == "active"


def test_update_member_non_self_raises_403(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    with pytest.raises(MembershipForbiddenException):
        service.update_member(user, chat_id=1, member_id=2, new_status="active")


def test_update_member_owner_cannot_change_own_status(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    with pytest.raises(CannotRemoveOwnerException):
        service.update_member(user, chat_id=1, member_id=1, new_status="inactive")


def test_update_member_invalid_transition_raises_validation_error(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    membership = make_membership(member_id=2, chat_id=1, status="active")
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.get_by_chat_and_member_for_update", return_value=membership)
    with pytest.raises(ValidationException):
        service.update_member(user, chat_id=1, member_id=2, new_status="pending")


def test_update_member_not_found_raises_404(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.get_by_chat_and_member_for_update", return_value=None)
    with pytest.raises(MembershipNotFoundException):
        service.update_member(user, chat_id=1, member_id=2, new_status="active")


def test_update_member_chat_not_found_raises_404(mocker):
    user = make_user(user_id=2)
    _patch_perms(mocker)
    _patch_chat_not_found(mocker)
    _patch_atomic(mocker)
    with pytest.raises(ChatNotFoundException):
        service.update_member(user, chat_id=999, member_id=2, new_status="active")


# ══════════════════════════════════════════════════════════════════════════════
# remove_member
# ══════════════════════════════════════════════════════════════════════════════

def test_remove_member_owner_role_can_remove(mocker):
    """A user with role=owner in the membership can remove members."""
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    membership = make_membership(member_id=2, chat_id=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=True)
    mocker.patch(f"{SVC}.membership_repository.get_by_chat_and_member_for_update", return_value=membership)
    soft_delete = mocker.patch(f"{SVC}.membership_repository.soft_delete")
    service.remove_member(user, chat_id=1, member_id=2)
    soft_delete.assert_called_once()


def test_remove_member_non_creator_with_owner_role_can_remove(mocker):
    """A non-creator user who has role=owner can also remove members."""
    user = make_user(user_id=5)
    chat = make_chat(chat_id=1, created_by=1)
    membership = make_membership(member_id=2, chat_id=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=True)
    mocker.patch(f"{SVC}.membership_repository.get_by_chat_and_member_for_update", return_value=membership)
    soft_delete = mocker.patch(f"{SVC}.membership_repository.soft_delete")
    service.remove_member(user, chat_id=1, member_id=2)
    soft_delete.assert_called_once()


def test_remove_member_regular_member_raises_403(mocker):
    """A user who is not role=owner cannot remove members."""
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    with pytest.raises(MembershipForbiddenException):
        service.remove_member(user, chat_id=1, member_id=3)


def test_remove_member_self_without_owner_role_raises_403(mocker):
    """A member trying to remove themselves via DELETE should be denied — use /leave/ instead."""
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    with pytest.raises(MembershipForbiddenException):
        service.remove_member(user, chat_id=1, member_id=2)


def test_remove_member_cannot_remove_creator_raises_403(mocker):
    """The chat creator (chat.created_by) can never be removed, even by another owner."""
    user = make_user(user_id=5)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    with pytest.raises(CannotRemoveOwnerException):
        service.remove_member(user, chat_id=1, member_id=1)


def test_remove_member_membership_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=True)
    mocker.patch(f"{SVC}.membership_repository.get_by_chat_and_member_for_update", return_value=None)
    with pytest.raises(MembershipNotFoundException):
        service.remove_member(user, chat_id=1, member_id=2)


def test_remove_member_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    _patch_chat_not_found(mocker)
    _patch_atomic(mocker)
    with pytest.raises(ChatNotFoundException):
        service.remove_member(user, chat_id=999, member_id=2)


# ══════════════════════════════════════════════════════════════════════════════
# leave_chat
# ══════════════════════════════════════════════════════════════════════════════

def test_leave_chat_member_can_leave(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    membership = make_membership(member_id=2, chat_id=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.get_by_chat_and_member_for_update", return_value=membership)
    soft_delete = mocker.patch(f"{SVC}.membership_repository.soft_delete")
    service.leave_chat(user, chat_id=1)
    soft_delete.assert_called_once()


def test_leave_chat_creator_raises_403(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    with pytest.raises(CannotRemoveOwnerException):
        service.leave_chat(user, chat_id=1)


def test_leave_chat_membership_not_found_raises_404(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.get_by_chat_and_member_for_update", return_value=None)
    with pytest.raises(MembershipNotFoundException):
        service.leave_chat(user, chat_id=1)


def test_leave_chat_chat_not_found_raises_404(mocker):
    user = make_user(user_id=2)
    _patch_perms(mocker)
    _patch_chat_not_found(mocker)
    _patch_atomic(mocker)
    with pytest.raises(ChatNotFoundException):
        service.leave_chat(user, chat_id=999)


def test_leave_chat_always_acts_on_own_user_id(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    membership = make_membership(member_id=2, chat_id=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    get_membership = mocker.patch(
        f"{SVC}.membership_repository.get_by_chat_and_member_for_update",
        return_value=membership,
    )
    mocker.patch(f"{SVC}.membership_repository.soft_delete")
    service.leave_chat(user, chat_id=1)
    get_membership.assert_called_once_with(1, 2)


# ══════════════════════════════════════════════════════════════════════════════
# update_member_role
# ══════════════════════════════════════════════════════════════════════════════

def test_update_member_role_creator_can_update(mocker):
    """The chat creator (chat.created_by) can update roles."""
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    updated = make_membership(member_id=2, chat_id=1, role="reader")
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    mocker.patch(f"{SVC}.membership_repository.update_role", return_value=updated)
    result = service.update_member_role(user, chat_id=1, member_id=2, role="reader")
    assert result.role == "reader"


def test_update_member_role_role_owner_can_update(mocker):
    """A non-creator user with role=owner can also update member roles."""
    user = make_user(user_id=5)
    chat = make_chat(chat_id=1, created_by=1)
    updated = make_membership(member_id=2, chat_id=1, role="reader")
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=True)
    mocker.patch(f"{SVC}.membership_repository.update_role", return_value=updated)
    result = service.update_member_role(user, chat_id=1, member_id=2, role="reader")
    assert result.role == "reader"


def test_update_member_role_regular_member_raises_403(mocker):
    """A user who is neither creator nor role=owner cannot update roles."""
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    with pytest.raises(RoleUpdateForbiddenException):
        service.update_member_role(user, chat_id=1, member_id=3, role="editor")


def test_update_member_role_cannot_update_creators_role(mocker):
    """The creator's role is always protected and cannot be changed."""
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    with pytest.raises(RoleUpdateForbiddenException):
        service.update_member_role(user, chat_id=1, member_id=1, role="editor")


def test_update_member_role_membership_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    mocker.patch(f"{SVC}.membership_repository.update_role", return_value=None)
    with pytest.raises(MembershipNotFoundException):
        service.update_member_role(user, chat_id=1, member_id=2, role="editor")


def test_update_member_role_chat_not_found_raises_404(mocker):
    user = make_user(user_id=1)
    _patch_perms(mocker)
    _patch_chat_not_found(mocker)
    _patch_atomic(mocker)
    with pytest.raises(ChatNotFoundException):
        service.update_member_role(user, chat_id=999, member_id=2, role="reader")


def test_update_member_role_calls_repo_with_correct_args(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    updated = make_membership(member_id=2, chat_id=1, role="reader")
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    repo = mocker.patch(f"{SVC}.membership_repository.update_role", return_value=updated)
    service.update_member_role(user, chat_id=1, member_id=2, role="reader")
    repo.assert_called_once_with(1, 2, "reader", updated_by=1)


# ══════════════════════════════════════════════════════════════════════════════
# add_members — IntegrityError fallback (TOCTOU race) + invite notification
# ══════════════════════════════════════════════════════════════════════════════

def test_add_members_create_integrity_error_raises_409(mocker):
    """The precheck passes but a concurrent insert makes create() hit the unique
    constraint — the IntegrityError is translated to a 409, not leaked."""
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    mocker.patch(f"{SVC}.membership_repository.get_existing_member_ids_in", return_value=set())
    mocker.patch(f"{SVC}.membership_repository.create", side_effect=IntegrityError())
    with pytest.raises(MembershipAlreadyExistsException):
        service.add_members(user, chat_id=1, member_ids=[2])


def test_add_members_emits_invite_notification(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1, name="Equipo")
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic_run_oncommit(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    mocker.patch(f"{SVC}.membership_repository.get_existing_member_ids_in", return_value=set())
    mocker.patch(f"{SVC}.membership_repository.create", side_effect=[
        make_membership(member_id=2),
        make_membership(member_id=3),
    ])
    emit = mocker.patch(f"{SVC}.notification_client.emit_event")
    service.add_members(user, chat_id=1, member_ids=[2, 3])
    emit.assert_called_once()
    _, kwargs = emit.call_args
    assert kwargs["event_type"] == "chat.member.invited"
    assert set(kwargs["recipient_ids"]) == {2, 3}
    assert kwargs["actor_id"] == 1


def test_add_members_no_one_created_skips_notification(mocker):
    """An empty member_ids list creates nobody and emits no notification."""
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic_run_oncommit(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=False)
    mocker.patch(f"{SVC}.membership_repository.get_existing_member_ids_in", return_value=set())
    emit = mocker.patch(f"{SVC}.notification_client.emit_event")
    result = service.add_members(user, chat_id=1, member_ids=[])
    assert result == []
    emit.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# update_member — reactivation + WS broadcasts
# ══════════════════════════════════════════════════════════════════════════════

def test_update_member_active_status_broadcasts_member_joined(mocker):
    user = make_user(user_id=2)
    chat = make_chat(chat_id=1, created_by=1)
    membership = make_membership(member_id=2, chat_id=1, status="pending")
    updated = make_membership(member_id=2, chat_id=1, status="active")
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic_run_oncommit(mocker)
    mocker.patch(f"{SVC}.membership_repository.get_by_chat_and_member_for_update", return_value=membership)
    mocker.patch(f"{SVC}.membership_repository.update_status", return_value=updated)
    broadcast = mocker.patch(f"{SVC}._broadcast_member_joined")
    service.update_member(user, chat_id=1, member_id=2, new_status="active")
    broadcast.assert_called_once_with(1, 2)


# ══════════════════════════════════════════════════════════════════════════════
# remove_member — removed notification + member_left broadcast
# ══════════════════════════════════════════════════════════════════════════════

def test_remove_member_emits_removed_notification_and_broadcast(mocker):
    user = make_user(user_id=1)
    chat = make_chat(chat_id=1, created_by=1)
    membership = make_membership(member_id=2, chat_id=1)
    _patch_perms(mocker)
    _patch_chat(mocker, chat)
    _patch_atomic_run_oncommit(mocker)
    mocker.patch(f"{SVC}.membership_repository.is_chat_owner", return_value=True)
    mocker.patch(f"{SVC}.membership_repository.get_by_chat_and_member_for_update", return_value=membership)
    mocker.patch(f"{SVC}.membership_repository.soft_delete")
    broadcast = mocker.patch(f"{SVC}._broadcast_member_left")
    emit = mocker.patch(f"{SVC}.notification_client.emit_event")
    service.remove_member(user, chat_id=1, member_id=2)
    broadcast.assert_called_once_with(1, 2)
    emit.assert_called_once()
    _, kwargs = emit.call_args
    assert kwargs["event_type"] == "chat.member.removed"
    assert kwargs["recipient_ids"] == [2]
