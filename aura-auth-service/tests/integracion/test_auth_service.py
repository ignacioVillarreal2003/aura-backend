import uuid
from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import User, RefreshToken
from apps.accounts.services.auth_service import (
    authenticate_user,
    issue_tokens_for_user,
    revoke_all_sessions,
    revoke_refresh_token,
    rotate_refresh_token,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# TestAuthenticateUserIntegration
# ---------------------------------------------------------------------------

class TestAuthenticateUserIntegration:

    def test_valid_credentials_return_user(self, regular_user):
        result = authenticate_user("testuser", "testpass123")
        assert result is not None
        assert result.id == regular_user.id

    def test_resets_failed_attempts_on_success(self, regular_user):
        regular_user.failed_login_attempts = 3
        regular_user.save(update_fields=["failed_login_attempts"])
        authenticate_user("testuser", "testpass123")
        regular_user.refresh_from_db()
        assert regular_user.failed_login_attempts == 0

    def test_updates_last_login(self, regular_user):
        before = timezone.now()
        authenticate_user("testuser", "testpass123")
        regular_user.refresh_from_db()
        assert regular_user.last_login >= before

    def test_inactive_user_returns_none(self, regular_user):
        regular_user.status = "inactive"
        regular_user.save(update_fields=["status"])
        result = authenticate_user("testuser", "testpass123")
        assert result is None

    def test_deleted_user_returns_none(self, regular_user, bootstrap_user):
        regular_user.soft_delete(deleted_by=bootstrap_user)
        result = authenticate_user("testuser", "testpass123")
        assert result is None

    def test_wrong_password_increments_failed_attempts(self, regular_user):
        before = regular_user.failed_login_attempts or 0
        authenticate_user("testuser", "wrongpassword")
        regular_user.refresh_from_db()
        assert regular_user.failed_login_attempts > before

    def test_lockout_after_max_attempts(self, regular_user):
        for _ in range(settings.LOGIN_MAX_ATTEMPTS):
            authenticate_user("testuser", "badpassword")
        regular_user.refresh_from_db()
        assert regular_user.lockout_until is not None
        assert regular_user.lockout_until > timezone.now()


# ---------------------------------------------------------------------------
# TestTokenLifecycleIntegration
# ---------------------------------------------------------------------------

class TestTokenLifecycleIntegration:

    def test_issue_tokens_returns_dict(self, regular_user):
        result = issue_tokens_for_user(regular_user)
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "Bearer"

    def test_rotate_creates_new_token(self, regular_user):
        tokens = issue_tokens_for_user(regular_user)
        old_refresh = tokens["refresh_token"]
        new_tokens = rotate_refresh_token(old_refresh)
        assert new_tokens is not None
        assert new_tokens["refresh_token"] != old_refresh

    def test_rotate_revokes_old_token_in_db(self, regular_user):
        tokens = issue_tokens_for_user(regular_user)
        old_refresh = tokens["refresh_token"]
        rotate_refresh_token(old_refresh)
        old_row = RefreshToken.objects.get(token=old_refresh)
        assert old_row.is_revoked is True

    def test_revoke_marks_token_in_db(self, regular_user):
        tokens = issue_tokens_for_user(regular_user)
        refresh = tokens["refresh_token"]
        revoke_refresh_token(refresh)
        row = RefreshToken.objects.get(token=refresh)
        assert row.is_revoked is True

    def test_stolen_token_revokes_all_sessions(self, regular_user):
        issue_tokens_for_user(regular_user)
        issue_tokens_for_user(regular_user)
        first_tokens = issue_tokens_for_user(regular_user)
        rotate_refresh_token(first_tokens["refresh_token"])
        result = rotate_refresh_token(first_tokens["refresh_token"])
        assert result is None
        assert RefreshToken.objects.filter(user=regular_user, is_revoked=False).count() == 0

    def test_rotate_expired_token_returns_none(self, regular_user):
        refresh = RefreshToken.objects.create(
            token=str(uuid.uuid4()),
            user=regular_user,
            expires_at=timezone.now() - timedelta(seconds=1),
            is_revoked=False,
            created_by=regular_user.pk,
            updated_by=regular_user.pk,
        )
        result = rotate_refresh_token(str(refresh.token))
        assert result is None


# ---------------------------------------------------------------------------
# TestRevokeAllSessionsIntegration
# ---------------------------------------------------------------------------

class TestRevokeAllSessionsIntegration:

    def test_revokes_all_active_tokens(self, regular_user):
        issue_tokens_for_user(regular_user)
        issue_tokens_for_user(regular_user)
        revoke_all_sessions(regular_user)
        assert RefreshToken.objects.filter(user=regular_user, is_revoked=False).count() == 0

    def test_updates_tokens_valid_after(self, regular_user):
        revoke_all_sessions(regular_user)
        regular_user.refresh_from_db()
        assert regular_user.tokens_valid_after is not None

    def test_access_token_before_revocation_is_blocked(self, regular_user):
        from apps.accounts.services.auth_service import get_user_info
        tokens = issue_tokens_for_user(regular_user)
        revoke_all_sessions(regular_user)
        result = get_user_info(tokens["access_token"])
        assert result is None

    def test_new_token_after_revocation_is_valid(self, regular_user):
        revoke_all_sessions(regular_user)
        new_tokens = issue_tokens_for_user(regular_user)
        assert new_tokens["access_token"] is not None
        assert RefreshToken.objects.filter(user=regular_user, is_revoked=False).count() == 1
