import pytest

from apps.membership.exceptions import (
    CannotRemoveOwnerException,
    MembershipAlreadyExistsException,
    MembershipForbiddenException,
    MembershipNotFoundException,
    RoleUpdateForbiddenException,
)
from apps.membership.models.chat_membership import ChatMembership
from apps.membership.services.membership_service import membership_service
from core.exceptions import ValidationException

from .conftest import make_user

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# add_members
# ---------------------------------------------------------------------------

def test_add_members_creates_pending_memberships(owner, chat, member_user):
    memberships = membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    assert len(memberships) == 1
    db = ChatMembership.objects.get(chat_id=chat.id, member_id=member_user.id)
    assert db.status == ChatMembership.Status.PENDING


def test_add_members_multiple_creates_all(owner, chat):
    u2, u3 = make_user(id=1010), make_user(id=1011)
    memberships = membership_service.add_members(owner, chat.id, member_ids=[u2.id, u3.id])
    assert len(memberships) == 2
    assert ChatMembership.objects.filter(chat_id=chat.id, member_id__in=[u2.id, u3.id]).count() == 2


def test_add_members_already_active_raises(owner, chat, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    membership_service.update_member(member_user, chat.id, member_user.id, new_status="active")
    with pytest.raises(MembershipAlreadyExistsException):
        membership_service.add_members(owner, chat.id, member_ids=[member_user.id])


def test_add_members_non_owner_raises(chat, member_user, other_user):
    with pytest.raises(MembershipForbiddenException):
        membership_service.add_members(member_user, chat.id, member_ids=[other_user.id])


# ---------------------------------------------------------------------------
# update_member (status transitions)
# ---------------------------------------------------------------------------

def test_update_member_pending_to_active(owner, chat, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    membership_service.update_member(member_user, chat.id, member_user.id, new_status="active")
    db = ChatMembership.objects.get(chat_id=chat.id, member_id=member_user.id)
    assert db.status == ChatMembership.Status.ACTIVE


def test_update_member_active_to_inactive(owner, chat, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    membership_service.update_member(member_user, chat.id, member_user.id, new_status="active")
    membership_service.update_member(owner, chat.id, member_user.id, new_status="inactive")
    db = ChatMembership.objects.get(chat_id=chat.id, member_id=member_user.id)
    assert db.status == ChatMembership.Status.INACTIVE


def test_update_member_invalid_transition_raises(owner, chat, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    membership_service.update_member(member_user, chat.id, member_user.id, new_status="active")
    with pytest.raises(ValidationException):
        membership_service.update_member(owner, chat.id, member_user.id, new_status="pending")


def test_update_member_owner_status_cannot_change(owner, chat):
    with pytest.raises(CannotRemoveOwnerException):
        membership_service.update_member(owner, chat.id, owner.id, new_status="inactive")


def test_update_member_stranger_cannot_update(chat, member_user, other_user):
    membership_service.add_members(
        make_user(id=chat.created_by), chat.id, member_ids=[member_user.id]
    )
    with pytest.raises(MembershipForbiddenException):
        membership_service.update_member(other_user, chat.id, member_user.id, new_status="active")


# ---------------------------------------------------------------------------
# remove_member
# ---------------------------------------------------------------------------

def test_remove_member_soft_deletes_membership(owner, chat, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    membership_service.update_member(member_user, chat.id, member_user.id, new_status="active")
    membership_service.remove_member(owner, chat.id, member_user.id)
    assert not ChatMembership.objects.filter(chat_id=chat.id, member_id=member_user.id).exists()
    assert ChatMembership.objects.all_with_deleted().filter(
        chat_id=chat.id, member_id=member_user.id, deleted_at__isnull=False
    ).exists()


def test_remove_owner_raises(owner, chat):
    with pytest.raises(CannotRemoveOwnerException):
        membership_service.remove_member(owner, chat.id, owner.id)


def test_remove_member_stranger_raises(chat, member_user, other_user):
    membership_service.add_members(
        make_user(id=chat.created_by), chat.id, member_ids=[member_user.id]
    )
    with pytest.raises(MembershipForbiddenException):
        membership_service.remove_member(other_user, chat.id, member_user.id)


# ---------------------------------------------------------------------------
# leave_chat
# ---------------------------------------------------------------------------

def test_leave_chat_soft_deletes_membership(owner, chat, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    membership_service.update_member(member_user, chat.id, member_user.id, new_status="active")
    membership_service.leave_chat(member_user, chat.id)
    assert not ChatMembership.objects.filter(chat_id=chat.id, member_id=member_user.id).exists()


def test_leave_chat_owner_raises(owner, chat):
    with pytest.raises(CannotRemoveOwnerException):
        membership_service.leave_chat(owner, chat.id)


def test_leave_chat_non_member_raises(chat, other_user):
    with pytest.raises(MembershipNotFoundException):
        membership_service.leave_chat(other_user, chat.id)


# ---------------------------------------------------------------------------
# update_member_role
# ---------------------------------------------------------------------------

def test_update_member_role_persists(owner, chat, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    membership_service.update_member(member_user, chat.id, member_user.id, new_status="active")
    membership_service.update_member_role(owner, chat.id, member_user.id, role="reader")
    db = ChatMembership.objects.get(chat_id=chat.id, member_id=member_user.id)
    assert db.role == ChatMembership.Role.READER


def test_update_owner_role_raises(owner, chat):
    with pytest.raises(RoleUpdateForbiddenException):
        membership_service.update_member_role(owner, chat.id, owner.id, role="editor")


def test_update_role_non_owner_raises(chat, member_user, other_user):
    membership_service.add_members(
        make_user(id=chat.created_by), chat.id, member_ids=[member_user.id]
    )
    with pytest.raises(RoleUpdateForbiddenException):
        membership_service.update_member_role(other_user, chat.id, member_user.id, role="reader")


# ---------------------------------------------------------------------------
# list_members
# ---------------------------------------------------------------------------

def test_list_members_returns_active_by_default(owner, chat, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    membership_service.update_member(member_user, chat.id, member_user.id, new_status="active")
    members = list(membership_service.list_members(owner, chat.id))
    member_ids = [m.member_id for m in members]
    assert owner.id in member_ids
    assert member_user.id in member_ids


def test_list_members_pending_not_in_active_filter(owner, chat, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    members = list(membership_service.list_members(owner, chat.id, status="active"))
    member_ids = [m.member_id for m in members]
    assert member_user.id not in member_ids


def test_list_members_all_includes_pending(owner, chat, member_user):
    membership_service.add_members(owner, chat.id, member_ids=[member_user.id])
    members = list(membership_service.list_members(owner, chat.id, status=None))
    member_ids = [m.member_id for m in members]
    assert member_user.id in member_ids
