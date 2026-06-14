"""
Membership views — HTTP layer tests

Endpoints covered:
    GET    /api/v1/chats/{chat_id}/members/                  MemberListView.get
    POST   /api/v1/chats/{chat_id}/members/                  MemberListView.post
    GET    /api/v1/chats/{chat_id}/members/manage/           AdminMemberListView.get
    PATCH  /api/v1/chats/{chat_id}/members/{member_id}/      MemberDetailView.patch
    DELETE /api/v1/chats/{chat_id}/members/{member_id}/      MemberDetailView.delete
    POST   /api/v1/chats/{chat_id}/members/leave/            LeaveChatView.post
    PATCH  /api/v1/chats/{chat_id}/members/{member_id}/role/ RoleUpdateView.patch
    GET    /api/v1/memberships/me/                           MyMembershipsView.get
"""
from apps.chat.exceptions import ChatNotFoundException
from apps.membership.exceptions import (
    CannotRemoveOwnerException,
    MembershipAlreadyExistsException,
    MembershipForbiddenException,
    MembershipNotFoundException,
    RoleUpdateForbiddenException,
)
from core.exceptions import ValidationException
from core.exceptions.base import InsufficientPermissionsException
from test.conftest import make_membership

MEMBER_VIEW = "apps.membership.views.membership_view"
ROLE_VIEW = "apps.membership.views.role_view"


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/chats/{chat_id}/members/
# ══════════════════════════════════════════════════════════════════════════════

def test_list_members_returns_200_paginated(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.list_members",
        return_value=[make_membership()],
    )
    response = api_client.get("/api/v1/chats/1/members/")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1


def test_list_members_empty_returns_200(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.list_members", return_value=[])
    response = api_client.get("/api/v1/chats/1/members/")
    assert response.status_code == 200
    assert response.data["results"] == []


def test_list_members_default_status_is_active(api_client, mocker):
    svc = mocker.patch(f"{MEMBER_VIEW}.membership_service.list_members", return_value=[])
    api_client.get("/api/v1/chats/1/members/")
    _, kwargs = svc.call_args
    assert kwargs["status"] == "active"


def test_list_members_status_filter_forwarded(api_client, mocker):
    svc = mocker.patch(f"{MEMBER_VIEW}.membership_service.list_members", return_value=[])
    api_client.get("/api/v1/chats/1/members/?status=pending")
    _, kwargs = svc.call_args
    assert kwargs["status"] == "pending"


def test_list_members_status_all_sends_none(api_client, mocker):
    svc = mocker.patch(f"{MEMBER_VIEW}.membership_service.list_members", return_value=[])
    api_client.get("/api/v1/chats/1/members/?status=all")
    _, kwargs = svc.call_args
    assert kwargs["status"] is None


def test_list_members_invalid_status_returns_400(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.list_members")
    response = api_client.get("/api/v1/chats/1/members/?status=banned")
    assert response.status_code == 400
    assert response.data["error"] == "invalid_status"


def test_list_members_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.list_members",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.get("/api/v1/chats/999/members/")
    assert response.status_code == 404


def test_list_members_not_member_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.list_members",
        side_effect=MembershipForbiddenException(),
    )
    response = api_client.get("/api/v1/chats/1/members/")
    assert response.status_code == 403
    assert response.data["error"] == "membership_forbidden"


def test_list_members_insufficient_permissions_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.list_members",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/chats/1/members/")
    assert response.status_code == 403


def test_list_members_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/chats/1/members/")
    assert response.status_code == 401


def test_list_members_response_shape(api_client, mocker):
    membership = make_membership(member_id=2, chat_id=1, status="active", role="editor")
    mocker.patch(f"{MEMBER_VIEW}.membership_service.list_members", return_value=[membership])
    response = api_client.get("/api/v1/chats/1/members/")
    result = response.data["results"][0]
    for field in ("id", "member_id", "chat_id", "status", "role", "joined_at", "created_by", "created_at"):
        assert field in result, f"Missing field: {field}"


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/chats/{chat_id}/members/
# ══════════════════════════════════════════════════════════════════════════════

def test_invite_members_returns_201(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.add_members",
        return_value=[make_membership(member_id=2), make_membership(member_id=3)],
    )
    response = api_client.post(
        "/api/v1/chats/1/members/",
        {"member_ids": [2, 3]},
        format="json",
    )
    assert response.status_code == 201
    assert len(response.data) == 2


def test_invite_members_empty_list_returns_400(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.add_members")
    response = api_client.post("/api/v1/chats/1/members/", {"member_ids": []}, format="json")
    assert response.status_code == 400


def test_invite_members_missing_field_returns_400(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.add_members")
    response = api_client.post("/api/v1/chats/1/members/", {}, format="json")
    assert response.status_code == 400


def test_invite_members_deduplicates_ids(api_client, mocker):
    svc = mocker.patch(
        f"{MEMBER_VIEW}.membership_service.add_members",
        return_value=[make_membership(member_id=2)],
    )
    api_client.post("/api/v1/chats/1/members/", {"member_ids": [2, 2, 3]}, format="json")
    _, kwargs = svc.call_args
    assert kwargs["member_ids"].count(2) == 1


def test_invite_members_already_exists_returns_409(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.add_members",
        side_effect=MembershipAlreadyExistsException(),
    )
    response = api_client.post("/api/v1/chats/1/members/", {"member_ids": [2]}, format="json")
    assert response.status_code == 409
    assert response.data["error"] == "membership_already_exists"


def test_invite_members_non_owner_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.add_members",
        side_effect=MembershipForbiddenException(),
    )
    response = api_client.post("/api/v1/chats/1/members/", {"member_ids": [2]}, format="json")
    assert response.status_code == 403
    assert response.data["error"] == "membership_forbidden"


def test_invite_members_insufficient_permissions_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.add_members",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.post("/api/v1/chats/1/members/", {"member_ids": [2]}, format="json")
    assert response.status_code == 403


def test_invite_members_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.add_members",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.post("/api/v1/chats/999/members/", {"member_ids": [2]}, format="json")
    assert response.status_code == 404


def test_invite_members_unauthenticated_returns_401(anon_client):
    response = anon_client.post("/api/v1/chats/1/members/", {"member_ids": [2]}, format="json")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/chats/{chat_id}/members/manage/
# ══════════════════════════════════════════════════════════════════════════════

def test_admin_list_members_returns_200_paginated(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.list_members_admin",
        return_value=[make_membership(), make_membership(member_id=3)],
    )
    response = api_client.get("/api/v1/chats/1/members/manage/")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 2


def test_admin_list_members_no_status_returns_all(api_client, mocker):
    svc = mocker.patch(f"{MEMBER_VIEW}.membership_service.list_members_admin", return_value=[])
    api_client.get("/api/v1/chats/1/members/manage/")
    _, kwargs = svc.call_args
    assert kwargs["status"] is None


def test_admin_list_members_status_all_sends_none(api_client, mocker):
    svc = mocker.patch(f"{MEMBER_VIEW}.membership_service.list_members_admin", return_value=[])
    api_client.get("/api/v1/chats/1/members/manage/?status=all")
    _, kwargs = svc.call_args
    assert kwargs["status"] is None


def test_admin_list_members_status_filter_forwarded(api_client, mocker):
    svc = mocker.patch(f"{MEMBER_VIEW}.membership_service.list_members_admin", return_value=[])
    api_client.get("/api/v1/chats/1/members/manage/?status=pending")
    _, kwargs = svc.call_args
    assert kwargs["status"] == "pending"


def test_admin_list_members_invalid_status_returns_400(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.list_members_admin")
    response = api_client.get("/api/v1/chats/1/members/manage/?status=unknown")
    assert response.status_code == 400


def test_admin_list_members_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.list_members_admin",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.get("/api/v1/chats/999/members/manage/")
    assert response.status_code == 404


def test_admin_list_members_insufficient_permissions_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.list_members_admin",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/chats/1/members/manage/")
    assert response.status_code == 403


def test_admin_list_members_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/chats/1/members/manage/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /api/v1/chats/{chat_id}/members/{member_id}/
# ══════════════════════════════════════════════════════════════════════════════

def test_update_member_status_returns_200(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.update_member",
        return_value=make_membership(status="active"),
    )
    response = api_client.patch(
        "/api/v1/chats/1/members/2/",
        {"status": "active"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["status"] == "active"


def test_update_member_status_invalid_value_returns_400(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.update_member")
    response = api_client.patch(
        "/api/v1/chats/1/members/2/",
        {"status": "banned"},
        format="json",
    )
    assert response.status_code == 400


def test_update_member_status_missing_field_returns_400(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.update_member")
    response = api_client.patch("/api/v1/chats/1/members/2/", {}, format="json")
    assert response.status_code == 400


def test_update_member_status_invalid_transition_returns_400(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.update_member",
        side_effect=ValidationException(detail="bad transition", error_code="invalid_status_transition"),
    )
    response = api_client.patch(
        "/api/v1/chats/1/members/2/",
        {"status": "active"},
        format="json",
    )
    assert response.status_code == 400
    assert response.data["error"] == "invalid_status_transition"


def test_update_member_status_non_self_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.update_member",
        side_effect=MembershipForbiddenException(),
    )
    response = api_client.patch(
        "/api/v1/chats/1/members/2/",
        {"status": "active"},
        format="json",
    )
    assert response.status_code == 403
    assert response.data["error"] == "membership_forbidden"


def test_update_member_status_owner_cannot_change_own_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.update_member",
        side_effect=CannotRemoveOwnerException(),
    )
    response = api_client.patch(
        "/api/v1/chats/1/members/1/",
        {"status": "active"},
        format="json",
    )
    assert response.status_code == 403
    assert response.data["error"] == "cannot_remove_owner"


def test_update_member_status_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.update_member",
        side_effect=MembershipNotFoundException(),
    )
    response = api_client.patch(
        "/api/v1/chats/1/members/999/",
        {"status": "active"},
        format="json",
    )
    assert response.status_code == 404
    assert response.data["error"] == "membership_not_found"


def test_update_member_status_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.update_member",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.patch(
        "/api/v1/chats/999/members/2/",
        {"status": "active"},
        format="json",
    )
    assert response.status_code == 404


def test_update_member_status_unauthenticated_returns_401(anon_client):
    response = anon_client.patch(
        "/api/v1/chats/1/members/2/",
        {"status": "active"},
        format="json",
    )
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /api/v1/chats/{chat_id}/members/{member_id}/
# ══════════════════════════════════════════════════════════════════════════════

def test_remove_member_returns_204(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.remove_member")
    response = api_client.delete("/api/v1/chats/1/members/2/")
    assert response.status_code == 204


def test_remove_member_non_owner_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.remove_member",
        side_effect=MembershipForbiddenException(),
    )
    response = api_client.delete("/api/v1/chats/1/members/2/")
    assert response.status_code == 403
    assert response.data["error"] == "membership_forbidden"


def test_remove_member_cannot_remove_owner_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.remove_member",
        side_effect=CannotRemoveOwnerException(),
    )
    response = api_client.delete("/api/v1/chats/1/members/1/")
    assert response.status_code == 403
    assert response.data["error"] == "cannot_remove_owner"


def test_remove_member_insufficient_permissions_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.remove_member",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.delete("/api/v1/chats/1/members/2/")
    assert response.status_code == 403


def test_remove_member_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.remove_member",
        side_effect=MembershipNotFoundException(),
    )
    response = api_client.delete("/api/v1/chats/1/members/999/")
    assert response.status_code == 404
    assert response.data["error"] == "membership_not_found"


def test_remove_member_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.remove_member",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.delete("/api/v1/chats/999/members/2/")
    assert response.status_code == 404


def test_remove_member_unauthenticated_returns_401(anon_client):
    response = anon_client.delete("/api/v1/chats/1/members/2/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/chats/{chat_id}/members/leave/
# ══════════════════════════════════════════════════════════════════════════════

def test_leave_chat_returns_204(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.leave_chat")
    response = api_client.post("/api/v1/chats/1/members/leave/")
    assert response.status_code == 204


def test_leave_chat_creator_cannot_leave_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.leave_chat",
        side_effect=CannotRemoveOwnerException(),
    )
    response = api_client.post("/api/v1/chats/1/members/leave/")
    assert response.status_code == 403
    assert response.data["error"] == "cannot_remove_owner"


def test_leave_chat_not_member_returns_404(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.leave_chat",
        side_effect=MembershipNotFoundException(),
    )
    response = api_client.post("/api/v1/chats/1/members/leave/")
    assert response.status_code == 404
    assert response.data["error"] == "membership_not_found"


def test_leave_chat_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.leave_chat",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.post("/api/v1/chats/999/members/leave/")
    assert response.status_code == 404


def test_leave_chat_insufficient_permissions_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.leave_chat",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.post("/api/v1/chats/1/members/leave/")
    assert response.status_code == 403


def test_leave_chat_unauthenticated_returns_401(anon_client):
    response = anon_client.post("/api/v1/chats/1/members/leave/")
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /api/v1/chats/{chat_id}/members/{member_id}/role/
# ══════════════════════════════════════════════════════════════════════════════

def test_update_role_returns_200(api_client, mocker):
    mocker.patch(
        f"{ROLE_VIEW}.membership_service.update_member_role",
        return_value=make_membership(role="reader"),
    )
    response = api_client.patch(
        "/api/v1/chats/1/members/2/role/",
        {"role": "reader"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["role"] == "reader"


def test_update_role_to_editor_returns_200(api_client, mocker):
    mocker.patch(
        f"{ROLE_VIEW}.membership_service.update_member_role",
        return_value=make_membership(role="editor"),
    )
    response = api_client.patch(
        "/api/v1/chats/1/members/2/role/",
        {"role": "editor"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["role"] == "editor"


def test_update_role_invalid_role_returns_400(api_client, mocker):
    mocker.patch(f"{ROLE_VIEW}.membership_service.update_member_role")
    response = api_client.patch(
        "/api/v1/chats/1/members/2/role/",
        {"role": "superadmin"},
        format="json",
    )
    assert response.status_code == 400


def test_update_role_missing_field_returns_400(api_client, mocker):
    mocker.patch(f"{ROLE_VIEW}.membership_service.update_member_role")
    response = api_client.patch("/api/v1/chats/1/members/2/role/", {}, format="json")
    assert response.status_code == 400


def test_update_role_non_owner_returns_403(api_client, mocker):
    mocker.patch(
        f"{ROLE_VIEW}.membership_service.update_member_role",
        side_effect=RoleUpdateForbiddenException(),
    )
    response = api_client.patch(
        "/api/v1/chats/1/members/2/role/",
        {"role": "reader"},
        format="json",
    )
    assert response.status_code == 403
    assert response.data["error"] == "role_update_forbidden"


def test_update_role_cannot_update_owner_returns_403(api_client, mocker):
    mocker.patch(
        f"{ROLE_VIEW}.membership_service.update_member_role",
        side_effect=RoleUpdateForbiddenException(),
    )
    response = api_client.patch(
        "/api/v1/chats/1/members/1/role/",
        {"role": "editor"},
        format="json",
    )
    assert response.status_code == 403
    assert response.data["error"] == "role_update_forbidden"


def test_update_role_insufficient_permissions_returns_403(api_client, mocker):
    mocker.patch(
        f"{ROLE_VIEW}.membership_service.update_member_role",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.patch(
        "/api/v1/chats/1/members/2/role/",
        {"role": "editor"},
        format="json",
    )
    assert response.status_code == 403


def test_update_role_membership_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{ROLE_VIEW}.membership_service.update_member_role",
        side_effect=MembershipNotFoundException(),
    )
    response = api_client.patch(
        "/api/v1/chats/1/members/999/role/",
        {"role": "editor"},
        format="json",
    )
    assert response.status_code == 404
    assert response.data["error"] == "membership_not_found"


def test_update_role_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{ROLE_VIEW}.membership_service.update_member_role",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.patch(
        "/api/v1/chats/999/members/2/role/",
        {"role": "editor"},
        format="json",
    )
    assert response.status_code == 404


def test_update_role_unauthenticated_returns_401(anon_client):
    response = anon_client.patch(
        "/api/v1/chats/1/members/2/role/",
        {"role": "reader"},
        format="json",
    )
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/memberships/me/
# ══════════════════════════════════════════════════════════════════════════════

def test_my_memberships_returns_200_paginated(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.list_my_memberships",
        return_value=[make_membership(member_id=1)],
    )
    response = api_client.get("/api/v1/memberships/me/")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1


def test_my_memberships_empty_returns_200(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.list_my_memberships", return_value=[])
    response = api_client.get("/api/v1/memberships/me/")
    assert response.status_code == 200
    assert response.data["results"] == []


def test_my_memberships_no_status_sends_none(api_client, mocker):
    svc = mocker.patch(f"{MEMBER_VIEW}.membership_service.list_my_memberships", return_value=[])
    api_client.get("/api/v1/memberships/me/")
    _, kwargs = svc.call_args
    assert kwargs["status"] is None


def test_my_memberships_status_pending_forwarded(api_client, mocker):
    svc = mocker.patch(f"{MEMBER_VIEW}.membership_service.list_my_memberships", return_value=[])
    api_client.get("/api/v1/memberships/me/?status=pending")
    _, kwargs = svc.call_args
    assert kwargs["status"] == "pending"


def test_my_memberships_invalid_status_returns_400(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.list_my_memberships")
    response = api_client.get("/api/v1/memberships/me/?status=banned")
    assert response.status_code == 400
    assert response.data["error"] == "invalid_status"


def test_my_memberships_insufficient_permissions_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.list_my_memberships",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get("/api/v1/memberships/me/")
    assert response.status_code == 403


def test_my_memberships_unauthenticated_returns_401(anon_client):
    response = anon_client.get("/api/v1/memberships/me/")
    assert response.status_code == 401


def test_my_memberships_response_shape(api_client, mocker):
    membership = make_membership(member_id=1, chat_id=5, status="active", role="editor")
    mocker.patch(f"{MEMBER_VIEW}.membership_service.list_my_memberships", return_value=[membership])
    response = api_client.get("/api/v1/memberships/me/")
    result = response.data["results"][0]
    for field in ("id", "member_id", "chat_id", "status", "role", "joined_at", "created_by", "created_at"):
        assert field in result, f"Missing field: {field}"
