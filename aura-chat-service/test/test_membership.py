from apps.chat.exceptions import ChatNotFoundException
from apps.membership.exceptions import (
    CannotRemoveOwnerException,
    MembershipAlreadyExistsException,
    MembershipForbiddenException,
    MembershipNotFoundException,
    RoleUpdateForbiddenException,
)
from test.conftest import make_membership


MEMBER_VIEW = "apps.membership.views.membership_view"
ROLE_VIEW = "apps.membership.views.role_view"


# ---------------------------------------------------------------------------
# List members  GET /api/v1/chats/{chat_id}/members/
# ---------------------------------------------------------------------------

def test_list_members_returns_200(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.list_members",
        return_value=[make_membership()],
    )
    response = api_client.get("/api/v1/chats/1/members/")
    assert response.status_code == 200
    assert "results" in response.data
    assert len(response.data["results"]) == 1


def test_list_members_with_status_filter(api_client, mocker):
    svc = mocker.patch(
        f"{MEMBER_VIEW}.membership_service.list_members",
        return_value=[],
    )
    api_client.get("/api/v1/chats/1/members/?status=active")
    _, kwargs = svc.call_args
    assert kwargs["status"] == "active"


def test_list_members_with_all_status(api_client, mocker):
    svc = mocker.patch(
        f"{MEMBER_VIEW}.membership_service.list_members",
        return_value=[],
    )
    api_client.get("/api/v1/chats/1/members/?status=all")
    _, kwargs = svc.call_args
    assert kwargs["status"] is None


def test_list_members_invalid_status_returns_400(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.list_members")
    response = api_client.get("/api/v1/chats/1/members/?status=banned")
    assert response.status_code == 400
    assert response.data["error"] == "invalid_status"


def test_list_members_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.list_members",
        side_effect=MembershipForbiddenException(),
    )
    response = api_client.get("/api/v1/chats/1/members/")
    assert response.status_code == 403
    assert response.data["error"] == "membership_forbidden"


def test_list_members_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.list_members",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.get("/api/v1/chats/999/members/")
    assert response.status_code == 404


def test_list_members_unauthenticated(anon_client):
    response = anon_client.get("/api/v1/chats/1/members/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Invite members  POST /api/v1/chats/{chat_id}/members/
# ---------------------------------------------------------------------------

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


def test_invite_members_empty_ids_returns_400(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.add_members")
    response = api_client.post(
        "/api/v1/chats/1/members/",
        {"member_ids": []},
        format="json",
    )
    assert response.status_code == 400


def test_invite_members_missing_ids_returns_400(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.add_members")
    response = api_client.post("/api/v1/chats/1/members/", {}, format="json")
    assert response.status_code == 400


def test_invite_members_deduplicates_ids(api_client, mocker):
    svc = mocker.patch(
        f"{MEMBER_VIEW}.membership_service.add_members",
        return_value=[make_membership()],
    )
    api_client.post(
        "/api/v1/chats/1/members/",
        {"member_ids": [2, 2, 3]},
        format="json",
    )
    _, kwargs = svc.call_args
    assert kwargs["member_ids"].count(2) == 1


def test_invite_members_already_exists_returns_409(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.add_members",
        side_effect=MembershipAlreadyExistsException(),
    )
    response = api_client.post(
        "/api/v1/chats/1/members/",
        {"member_ids": [2]},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["error"] == "membership_already_exists"


def test_invite_members_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.add_members",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.post(
        "/api/v1/chats/999/members/",
        {"member_ids": [2]},
        format="json",
    )
    assert response.status_code == 404


def test_invite_members_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.add_members",
        side_effect=MembershipForbiddenException(),
    )
    response = api_client.post(
        "/api/v1/chats/1/members/",
        {"member_ids": [2]},
        format="json",
    )
    assert response.status_code == 403


def test_invite_members_unauthenticated(anon_client):
    response = anon_client.post(
        "/api/v1/chats/1/members/",
        {"member_ids": [2]},
        format="json",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Update member status  PATCH /api/v1/chats/{chat_id}/members/{member_id}/
# ---------------------------------------------------------------------------

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


def test_update_member_invalid_status_returns_400(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.update_member")
    response = api_client.patch(
        "/api/v1/chats/1/members/2/",
        {"status": "banned"},
        format="json",
    )
    assert response.status_code == 400


def test_update_member_not_found_returns_404(api_client, mocker):
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


def test_update_member_access_denied_returns_403(api_client, mocker):
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


# ---------------------------------------------------------------------------
# Remove member  DELETE /api/v1/chats/{chat_id}/members/{member_id}/
# ---------------------------------------------------------------------------

def test_remove_member_returns_204(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.remove_member")
    response = api_client.delete("/api/v1/chats/1/members/2/")
    assert response.status_code == 204


def test_remove_member_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.remove_member",
        side_effect=MembershipNotFoundException(),
    )
    response = api_client.delete("/api/v1/chats/1/members/999/")
    assert response.status_code == 404


def test_remove_member_cannot_remove_owner_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.remove_member",
        side_effect=CannotRemoveOwnerException(),
    )
    response = api_client.delete("/api/v1/chats/1/members/1/")
    assert response.status_code == 403
    assert response.data["error"] == "cannot_remove_owner"


def test_remove_member_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.remove_member",
        side_effect=MembershipForbiddenException(),
    )
    response = api_client.delete("/api/v1/chats/1/members/2/")
    assert response.status_code == 403


def test_remove_member_unauthenticated(anon_client):
    response = anon_client.delete("/api/v1/chats/1/members/2/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Leave chat  POST /api/v1/chats/{chat_id}/members/leave/
# ---------------------------------------------------------------------------

def test_leave_chat_returns_204(api_client, mocker):
    mocker.patch(f"{MEMBER_VIEW}.membership_service.leave_chat")
    response = api_client.post("/api/v1/chats/1/members/leave/")
    assert response.status_code == 204


def test_leave_chat_not_found_returns_404(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.leave_chat",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.post("/api/v1/chats/999/members/leave/")
    assert response.status_code == 404


def test_leave_chat_access_denied_returns_403(api_client, mocker):
    mocker.patch(
        f"{MEMBER_VIEW}.membership_service.leave_chat",
        side_effect=MembershipForbiddenException(),
    )
    response = api_client.post("/api/v1/chats/1/members/leave/")
    assert response.status_code == 403


def test_leave_chat_unauthenticated(anon_client):
    response = anon_client.post("/api/v1/chats/1/members/leave/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Update member role  PATCH /api/v1/chats/{chat_id}/members/{member_id}/role/
# ---------------------------------------------------------------------------

def test_update_member_role_returns_200(api_client, mocker):
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


def test_update_member_role_invalid_role_returns_400(api_client, mocker):
    mocker.patch(f"{ROLE_VIEW}.membership_service.update_member_role")
    response = api_client.patch(
        "/api/v1/chats/1/members/2/role/",
        {"role": "superadmin"},
        format="json",
    )
    assert response.status_code == 400


def test_update_member_role_not_found_returns_404(api_client, mocker):
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


def test_update_member_role_forbidden_returns_403(api_client, mocker):
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


def test_update_member_role_unauthenticated(anon_client):
    response = anon_client.patch(
        "/api/v1/chats/1/members/2/role/",
        {"role": "reader"},
        format="json",
    )
    assert response.status_code == 401
