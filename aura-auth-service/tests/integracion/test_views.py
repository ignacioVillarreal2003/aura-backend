import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.accounts.models import User, RefreshToken
from apps.accounts.services.auth_service import issue_tokens_for_user
from tests.conftest import make_access_token

pytestmark = pytest.mark.django_db

LOOKUP_URL = "/auth/users/lookup"
BY_IDS_URL = "/auth/users/by-ids"
CHANGE_PASSWORD_URL = "/auth/change-password"
LOGIN_URL = "/auth/login"


# ---------------------------------------------------------------------------
# TestUserLookupView
# ---------------------------------------------------------------------------

class TestUserLookupView:

    def test_missing_auth_returns_401(self, api_client):
        resp = api_client.get(LOOKUP_URL + "?q=john")
        assert resp.status_code == 401

    def test_regular_user_forbidden(self, api_client, regular_user):
        token = make_access_token(user_id=regular_user.id)
        resp = api_client.get(LOOKUP_URL + "?q=john", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 403

    def test_service_key_can_lookup_by_username(self, api_client, regular_user, svc_headers):
        resp = api_client.get(LOOKUP_URL + "?q=testuser", **svc_headers)
        assert resp.status_code == 200
        assert resp.data["count"] >= 1
        assert "testuser" in [r["username"] for r in resp.data["results"]]

    def test_service_key_can_lookup_by_email(self, api_client, regular_user, svc_headers):
        resp = api_client.get(LOOKUP_URL + "?q=test@example", **svc_headers)
        assert resp.status_code == 200
        assert resp.data["count"] >= 1

    def test_missing_q_returns_400(self, api_client, svc_headers):
        resp = api_client.get(LOOKUP_URL, **svc_headers)
        assert resp.status_code == 400

    def test_no_match_returns_empty(self, api_client, svc_headers):
        resp = api_client.get(LOOKUP_URL + "?q=xyzzzznobodymatch", **svc_headers)
        assert resp.status_code == 200
        assert resp.data["count"] == 0
        assert resp.data["results"] == []

    def test_lookup_by_name(self, api_client, bootstrap_user, svc_headers):
        User.objects.create_user(
            "nameduser", "named@example.com", "pass", created_by=bootstrap_user, name="John Doe"
        )
        resp = api_client.get(LOOKUP_URL + "?q=John", **svc_headers)
        assert resp.status_code == 200
        assert any(r["name"] == "John Doe" for r in resp.data["results"])

    def test_deleted_user_excluded_from_results(self, api_client, bootstrap_user, regular_user, svc_headers):
        regular_user.soft_delete(deleted_by=bootstrap_user)
        resp = api_client.get(LOOKUP_URL + "?q=testuser", **svc_headers)
        usernames = [r["username"] for r in resp.data["results"]]
        assert "testuser" not in usernames

    def test_inactive_user_excluded(self, api_client, regular_user, svc_headers):
        regular_user.status = "inactive"
        regular_user.save()
        resp = api_client.get(LOOKUP_URL + "?q=testuser", **svc_headers)
        assert regular_user.username not in [r["username"] for r in resp.data["results"]]

    def test_result_has_required_fields(self, api_client, regular_user, svc_headers):
        resp = api_client.get(LOOKUP_URL + "?q=testuser", **svc_headers)
        assert resp.status_code == 200
        for user_data in resp.data["results"]:
            assert "id" in user_data
            assert "username" in user_data
            assert "name" in user_data


# ---------------------------------------------------------------------------
# TestUsersByIdsView
# ---------------------------------------------------------------------------

class TestUsersByIdsView:

    def test_service_key_includes_email(self, api_client, regular_user, svc_headers):
        resp = api_client.get(f"{BY_IDS_URL}?ids={regular_user.id}", **svc_headers)
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["email"] == "test@example.com"

    def test_regular_user_hides_email(self, api_client, regular_user):
        token = make_access_token(user_id=regular_user.id)
        resp = api_client.get(
            f"{BY_IDS_URL}?ids={regular_user.id}", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        assert resp.status_code == 200
        assert "email" not in resp.data["results"][0]
        assert resp.data["results"][0]["username"] == "testuser"

    def test_missing_ids_returns_400(self, api_client, svc_headers):
        resp = api_client.get(BY_IDS_URL, **svc_headers)
        assert resp.status_code == 400

    def test_nonexistent_ids_return_empty(self, api_client, svc_headers):
        resp = api_client.get(f"{BY_IDS_URL}?ids=999999", **svc_headers)
        assert resp.status_code == 200
        assert resp.data["count"] == 0

    def test_multiple_ids(self, api_client, bootstrap_user, regular_user, svc_headers):
        user2 = User.objects.create_user(
            "user2", "user2@example.com", "pass", created_by=bootstrap_user
        )
        resp = api_client.get(f"{BY_IDS_URL}?ids={regular_user.id},{user2.id}", **svc_headers)
        assert resp.status_code == 200
        assert resp.data["count"] == 2

    def test_deleted_user_excluded(self, api_client, bootstrap_user, regular_user, svc_headers):
        regular_user.soft_delete(deleted_by=bootstrap_user)
        resp = api_client.get(f"{BY_IDS_URL}?ids={regular_user.id}", **svc_headers)
        assert resp.data["count"] == 0

    def test_invalid_ids_returns_400(self, api_client, svc_headers):
        resp = api_client.get(f"{BY_IDS_URL}?ids=abc", **svc_headers)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# TestChangePasswordViewIntegration
# ---------------------------------------------------------------------------

class TestChangePasswordViewIntegration:

    def test_change_password_ok(self, api_client, regular_user):
        tokens = issue_tokens_for_user(regular_user)
        resp = api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "testpass123", "new_password": "NewStrongPass1!"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}",
        )
        assert resp.status_code == 200

    def test_change_password_wrong_current_returns_400(self, api_client, regular_user):
        tokens = issue_tokens_for_user(regular_user)
        resp = api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "wrongpassword", "new_password": "NewStrongPass1!"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}",
        )
        assert resp.status_code == 400

    def test_change_password_unauthenticated_returns_401(self, api_client):
        resp = api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "old", "new_password": "NewStrongPass1!"},
            format="json",
        )
        assert resp.status_code == 401

    def test_change_password_missing_fields_returns_400(self, api_client, regular_user):
        tokens = issue_tokens_for_user(regular_user)
        resp = api_client.post(
            CHANGE_PASSWORD_URL,
            {},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}",
        )
        assert resp.status_code == 400

    def test_change_password_revokes_existing_tokens(self, api_client, regular_user):
        tokens = issue_tokens_for_user(regular_user)
        api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "testpass123", "new_password": "NewStrongPass1!"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}",
        )
        regular_user.refresh_from_db()
        assert RefreshToken.objects.filter(user=regular_user, is_revoked=False).count() == 0

    def test_change_password_new_password_works_for_login(self, api_client, regular_user):
        tokens = issue_tokens_for_user(regular_user)
        api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "testpass123", "new_password": "NewStrongPass1!"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}",
        )
        regular_user.refresh_from_db()
        assert regular_user.check_password("NewStrongPass1!")

    def test_change_password_old_password_no_longer_works(self, api_client, regular_user):
        tokens = issue_tokens_for_user(regular_user)
        api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "testpass123", "new_password": "NewStrongPass1!"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}",
        )
        regular_user.refresh_from_db()
        assert not regular_user.check_password("testpass123")

    def test_change_password_updates_tokens_valid_after(self, api_client, regular_user):
        tokens = issue_tokens_for_user(regular_user)
        api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "testpass123", "new_password": "NewStrongPass1!"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}",
        )
        regular_user.refresh_from_db()
        assert regular_user.tokens_valid_after is not None

    def test_change_password_missing_current_returns_400(self, api_client, regular_user):
        tokens = issue_tokens_for_user(regular_user)
        resp = api_client.post(
            CHANGE_PASSWORD_URL,
            {"new_password": "NewStrongPass1!"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}",
        )
        assert resp.status_code == 400

    def test_change_password_missing_new_returns_400(self, api_client, regular_user):
        tokens = issue_tokens_for_user(regular_user)
        resp = api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "testpass123"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}",
        )
        assert resp.status_code == 400
