"""
Internal chat-membership check — HTTP layer

Endpoint:
    GET /api/v1/internal/chats/{chat_id}/members/{user_id}/   InternalChatMembershipView.get

Verifies URL wiring, response serialization, error-status mapping and that the
endpoint requires authentication.
"""
from apps.chat.exceptions import ChatNotFoundException
from apps.membership.dtos import ChatMembershipCheck
from core.exceptions.base import InsufficientPermissionsException

INTERNAL_VIEW = "apps.membership.views.internal_membership_view"
URL = "/api/v1/internal/chats/1/members/5/"


def test_returns_200_with_membership_and_role(api_client, mocker):
    mocker.patch(
        f"{INTERNAL_VIEW}.membership_service.check_membership",
        return_value=ChatMembershipCheck(chat_id=1, user_id=5, is_member=True, role="owner"),
    )
    response = api_client.get(URL)
    assert response.status_code == 200
    assert response.data == {"chat_id": 1, "user_id": 5, "is_member": True, "role": "owner"}


def test_non_member_returns_200_is_member_false_null_role(api_client, mocker):
    mocker.patch(
        f"{INTERNAL_VIEW}.membership_service.check_membership",
        return_value=ChatMembershipCheck(chat_id=1, user_id=5, is_member=False, role=None),
    )
    response = api_client.get(URL)
    assert response.status_code == 200
    assert response.data["is_member"] is False
    assert response.data["role"] is None


def test_forwards_path_params_and_token_identity(api_client, mocker):
    svc = mocker.patch(
        f"{INTERNAL_VIEW}.membership_service.check_membership",
        return_value=ChatMembershipCheck(chat_id=1, user_id=5, is_member=False, role=None),
    )
    api_client.get(URL)
    _, kwargs = svc.call_args
    assert kwargs["chat_id"] == 1
    assert kwargs["user_id"] == 5
    assert kwargs["caller"].id == 1  # identity derived from the forwarded bearer token


def test_missing_chat_returns_404(api_client, mocker):
    mocker.patch(
        f"{INTERNAL_VIEW}.membership_service.check_membership",
        side_effect=ChatNotFoundException(),
    )
    response = api_client.get(URL)
    assert response.status_code == 404


def test_forbidden_caller_returns_403(api_client, mocker):
    mocker.patch(
        f"{INTERNAL_VIEW}.membership_service.check_membership",
        side_effect=InsufficientPermissionsException(),
    )
    response = api_client.get(URL)
    assert response.status_code == 403


def test_requires_authentication(anon_client):
    response = anon_client.get(URL)
    assert response.status_code == 401
