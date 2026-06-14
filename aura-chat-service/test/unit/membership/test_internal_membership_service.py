"""
Internal chat-membership check — service logic

Covers role resolution (implicit owner via created_by, owner/editor/reader →
owner/member), the non-member vs missing-chat distinction, and the
self vs admin authorization rules.
"""
import pytest

from apps.chat.exceptions import ChatNotFoundException
from apps.membership.services.membership_service import MembershipService
from core.exceptions.base import InsufficientPermissionsException
from test.conftest import make_chat, make_user

SVC = "apps.membership.services.membership_service"

service = MembershipService()


def _patch_chat(mocker, chat):
    return mocker.patch(f"{SVC}.chat_repository.get_by_id", return_value=chat)


def _patch_role(mocker, role):
    return mocker.patch(f"{SVC}.membership_repository.get_role", return_value=role)


# ──────────────────────────────────────────────────────────────────────────────
# role resolution
# ──────────────────────────────────────────────────────────────────────────────

def test_creator_is_implicit_owner_without_membership_query(mocker):
    caller = make_user(user_id=7)
    _patch_chat(mocker, make_chat(chat_id=1, created_by=7))
    get_role = _patch_role(mocker, None)

    result = service.check_membership(caller=caller, chat_id=1, user_id=7)

    assert (result.chat_id, result.user_id) == (1, 7)
    assert result.is_member is True
    assert result.role == "owner"
    get_role.assert_not_called()  # creator short-circuits the membership lookup


def test_active_owner_membership_maps_to_owner(mocker):
    caller = make_user(user_id=2)
    _patch_chat(mocker, make_chat(chat_id=1, created_by=1))
    _patch_role(mocker, "owner")

    result = service.check_membership(caller=caller, chat_id=1, user_id=2)

    assert (result.is_member, result.role) == (True, "owner")


@pytest.mark.parametrize("internal_role", ["editor", "reader"])
def test_active_non_owner_membership_exposes_granular_role(mocker, internal_role):
    caller = make_user(user_id=2)
    _patch_chat(mocker, make_chat(chat_id=1, created_by=1))
    _patch_role(mocker, internal_role)

    result = service.check_membership(caller=caller, chat_id=1, user_id=2)

    assert (result.is_member, result.role) == (True, internal_role)


def test_non_member_returns_is_member_false_and_null_role(mocker):
    caller = make_user(user_id=2)
    _patch_chat(mocker, make_chat(chat_id=1, created_by=1))
    _patch_role(mocker, None)

    result = service.check_membership(caller=caller, chat_id=1, user_id=2)

    assert result.is_member is False
    assert result.role is None


def test_missing_or_deleted_chat_raises_404(mocker):
    caller = make_user(user_id=2)
    _patch_chat(mocker, None)  # get_by_id excludes soft-deleted → None

    with pytest.raises(ChatNotFoundException):
        service.check_membership(caller=caller, chat_id=999, user_id=2)


# ──────────────────────────────────────────────────────────────────────────────
# authorization
# ──────────────────────────────────────────────────────────────────────────────

def test_self_query_allowed_without_manage_permission(mocker):
    caller = make_user(user_id=5, permissions=())  # no MANAGE_MEMBERS
    _patch_chat(mocker, make_chat(chat_id=1, created_by=1))
    _patch_role(mocker, "editor")

    result = service.check_membership(caller=caller, chat_id=1, user_id=5)

    assert result.is_member is True


def test_cross_user_query_without_manage_members_raises_403(mocker):
    caller = make_user(user_id=2, permissions=())
    chat_lookup = _patch_chat(mocker, make_chat(chat_id=1, created_by=1))

    with pytest.raises(InsufficientPermissionsException):
        service.check_membership(caller=caller, chat_id=1, user_id=5)

    # Fail closed: authorization is rejected before touching any data.
    chat_lookup.assert_not_called()


def test_cross_user_query_with_manage_members_allowed(mocker):
    caller = make_user(user_id=2, permissions=("MANAGE_MEMBERS",))
    _patch_chat(mocker, make_chat(chat_id=1, created_by=1))
    _patch_role(mocker, "owner")

    result = service.check_membership(caller=caller, chat_id=1, user_id=5)

    assert (result.is_member, result.role) == (True, "owner")
