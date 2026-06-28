import uuid
from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock, patch, call

import pytest
from django.utils import timezone

from tests.conftest import make_mock_user, make_access_token

_AUTH_SVC = "apps.accounts.services.auth_service"


# ---------------------------------------------------------------------------
# TestAuthenticateUser
# ---------------------------------------------------------------------------

class TestAuthenticateUser:

    @patch(f"{_AUTH_SVC}.authenticate")
    def test_valid_credentials_return_user(self, mock_auth):
        user = make_mock_user()
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_auth.return_value = user
        from apps.accounts.services.auth_service import authenticate_user
        result = authenticate_user("testuser", "pass")
        assert result == user

    @patch(f"{_AUTH_SVC}.authenticate")
    def test_invalid_credentials_return_none(self, mock_auth):
        mock_auth.return_value = None
        from apps.accounts.models import User as RealUser
        from apps.accounts.services.auth_service import authenticate_user
        with patch(f"{_AUTH_SVC}.User") as mock_user_cls:
            mock_user_cls.DoesNotExist = RealUser.DoesNotExist
            mock_user_cls.objects.get.side_effect = RealUser.DoesNotExist
            result = authenticate_user("testuser", "wrongpass")
        assert result is None

    @patch(f"{_AUTH_SVC}.authenticate")
    def test_deleted_user_returns_none(self, mock_auth):
        user = make_mock_user(is_deleted=True)
        type(user).is_deleted = PropertyMock(return_value=True)
        mock_auth.return_value = user
        from apps.accounts.services.auth_service import authenticate_user
        result = authenticate_user("testuser", "pass")
        assert result is None

    @patch(f"{_AUTH_SVC}.authenticate")
    def test_inactive_user_returns_none(self, mock_auth):
        user = make_mock_user(status="inactive")
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_auth.return_value = user
        from apps.accounts.services.auth_service import authenticate_user
        result = authenticate_user("testuser", "pass")
        assert result is None

    @patch(f"{_AUTH_SVC}.authenticate")
    def test_locked_account_returns_none(self, mock_auth):
        user = make_mock_user(account_non_locked=False)
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_auth.return_value = user
        from apps.accounts.services.auth_service import authenticate_user
        result = authenticate_user("testuser", "pass")
        assert result is None

    @patch(f"{_AUTH_SVC}.authenticate")
    def test_lockout_until_future_returns_none(self, mock_auth):
        user = make_mock_user(lockout_until=timezone.now() + timedelta(minutes=10))
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_auth.return_value = user
        from apps.accounts.services.auth_service import authenticate_user
        result = authenticate_user("testuser", "pass")
        assert result is None

    @patch(f"{_AUTH_SVC}.authenticate")
    def test_lockout_until_past_allows_login(self, mock_auth):
        user = make_mock_user(lockout_until=timezone.now() - timedelta(minutes=1))
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_auth.return_value = user
        from apps.accounts.services.auth_service import authenticate_user
        result = authenticate_user("testuser", "pass")
        assert result == user

    @patch(f"{_AUTH_SVC}.authenticate")
    def test_failed_login_increments_failed_attempts(self, mock_auth):
        mock_auth.return_value = None
        from apps.accounts.services.auth_service import authenticate_user
        with patch(f"{_AUTH_SVC}.User") as mock_user_cls:
            fake_u = MagicMock()
            fake_u.failed_login_attempts = 1
            mock_user_cls.objects.get.return_value = fake_u
            mock_user_cls.objects.filter.return_value.update.return_value = 1
            mock_user_cls.DoesNotExist = Exception
            authenticate_user("testuser", "wrongpass")
            mock_user_cls.objects.filter.assert_called()

    @patch(f"{_AUTH_SVC}.authenticate")
    def test_successful_login_resets_failed_attempts(self, mock_auth):
        user = make_mock_user()
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_auth.return_value = user
        from apps.accounts.services.auth_service import authenticate_user
        result = authenticate_user("testuser", "pass")
        assert result is not None
        user.save.assert_called()

    @patch(f"{_AUTH_SVC}.authenticate")
    def test_auth_returns_none_if_user_not_found_in_db(self, mock_auth):
        mock_auth.return_value = None
        from apps.accounts.services.auth_service import authenticate_user
        from django.core.exceptions import ObjectDoesNotExist
        with patch(f"{_AUTH_SVC}.User") as mock_user_cls:
            mock_user_cls.DoesNotExist = LookupError
            mock_user_cls.objects.get.side_effect = LookupError
            result = authenticate_user("ghost", "pass")
        assert result is None


# ---------------------------------------------------------------------------
# TestIssueTokensForUser
# ---------------------------------------------------------------------------

class TestIssueTokensForUser:

    def _mock_rt_qs(self):
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.update.return_value = 1
        return qs

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_returns_token_dict(self, mock_rt_cls):
        user = make_mock_user()
        type(user).is_superuser = PropertyMock(return_value=False)
        qs = self._mock_rt_qs()
        mock_rt_cls.objects.filter.return_value = qs
        token_val = str(uuid.uuid4())
        mock_refresh = MagicMock()
        mock_refresh.token = token_val
        mock_rt_cls.objects.create.return_value = mock_refresh
        from apps.accounts.services.auth_service import issue_tokens_for_user
        result = issue_tokens_for_user(user)
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "Bearer"
        assert result["refresh_token"] == token_val

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_revokes_existing_tokens(self, mock_rt_cls):
        user = make_mock_user()
        type(user).is_superuser = PropertyMock(return_value=False)
        qs = self._mock_rt_qs()
        mock_rt_cls.objects.filter.return_value = qs
        mock_refresh = MagicMock()
        mock_refresh.token = str(uuid.uuid4())
        mock_rt_cls.objects.create.return_value = mock_refresh
        from apps.accounts.services.auth_service import issue_tokens_for_user
        issue_tokens_for_user(user)
        mock_rt_cls.objects.filter.assert_called_once_with(user=user, is_revoked=False)
        qs.update.assert_called_once()

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_token_type_is_bearer(self, mock_rt_cls):
        user = make_mock_user()
        type(user).is_superuser = PropertyMock(return_value=False)
        qs = self._mock_rt_qs()
        mock_rt_cls.objects.filter.return_value = qs
        mock_rt_cls.objects.create.return_value = MagicMock(token=str(uuid.uuid4()))
        from apps.accounts.services.auth_service import issue_tokens_for_user
        result = issue_tokens_for_user(user)
        assert result["token_type"] == "Bearer"

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_access_token_is_string(self, mock_rt_cls):
        user = make_mock_user()
        type(user).is_superuser = PropertyMock(return_value=False)
        qs = self._mock_rt_qs()
        mock_rt_cls.objects.filter.return_value = qs
        mock_rt_cls.objects.create.return_value = MagicMock(token=str(uuid.uuid4()))
        from apps.accounts.services.auth_service import issue_tokens_for_user
        result = issue_tokens_for_user(user)
        assert isinstance(result["access_token"], str)

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_refresh_token_matches_db_value(self, mock_rt_cls):
        user = make_mock_user()
        type(user).is_superuser = PropertyMock(return_value=False)
        qs = self._mock_rt_qs()
        mock_rt_cls.objects.filter.return_value = qs
        token_val = str(uuid.uuid4())
        mock_rt_cls.objects.create.return_value = MagicMock(token=token_val)
        from apps.accounts.services.auth_service import issue_tokens_for_user
        result = issue_tokens_for_user(user)
        assert result["refresh_token"] == token_val

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_revocation_happens_before_new_token_created(self, mock_rt_cls):
        user = make_mock_user()
        type(user).is_superuser = PropertyMock(return_value=False)
        call_order = []
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.update.side_effect = lambda **kw: call_order.append("revoke")
        mock_rt_cls.objects.filter.return_value = qs
        mock_rt_cls.objects.create.side_effect = lambda **kw: (call_order.append("create"), MagicMock(token=str(uuid.uuid4())))[1]
        from apps.accounts.services.auth_service import issue_tokens_for_user
        issue_tokens_for_user(user)
        assert call_order.index("revoke") < call_order.index("create")


# ---------------------------------------------------------------------------
# TestRotateRefreshToken
# ---------------------------------------------------------------------------

class TestRotateRefreshToken:

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_valid_token_returns_new_pair(self, mock_rt_cls):
        user = make_mock_user()
        type(user).is_superuser = PropertyMock(return_value=False)
        old_refresh = MagicMock()
        old_refresh.is_revoked = False
        old_refresh.expires_at = timezone.now() + timedelta(days=1)
        old_refresh.user = user
        old_refresh.user.pk = user.pk
        new_token_val = str(uuid.uuid4())
        new_refresh = MagicMock()
        new_refresh.token = new_token_val
        mock_rt_cls.objects.filter.return_value.first.return_value = old_refresh
        mock_rt_cls.objects.filter.return_value.update.return_value = 1
        mock_rt_cls.objects.create.return_value = new_refresh
        from apps.accounts.services.auth_service import rotate_refresh_token
        result = rotate_refresh_token(str(uuid.uuid4()))
        assert result is not None
        assert "access_token" in result
        assert result["refresh_token"] == new_token_val

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_invalid_token_returns_none(self, mock_rt_cls):
        mock_rt_cls.objects.filter.return_value.first.return_value = None
        from apps.accounts.services.auth_service import rotate_refresh_token
        result = rotate_refresh_token(str(uuid.uuid4()))
        assert result is None

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_expired_token_returns_none(self, mock_rt_cls):
        user = make_mock_user()
        old_refresh = MagicMock()
        old_refresh.is_revoked = False
        old_refresh.expires_at = timezone.now() - timedelta(seconds=1)
        old_refresh.user = user
        old_refresh.user.pk = user.pk
        mock_rt_cls.objects.filter.return_value.first.return_value = old_refresh
        mock_rt_cls.objects.filter.return_value.update.return_value = 1
        from apps.accounts.services.auth_service import rotate_refresh_token
        result = rotate_refresh_token(str(uuid.uuid4()))
        assert result is None

    @patch(f"{_AUTH_SVC}.revoke_all_sessions")
    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_stolen_token_revokes_all_sessions(self, mock_rt_cls, mock_revoke_all):
        user = make_mock_user()
        stolen = MagicMock()
        stolen.is_revoked = True
        stolen.user = user
        mock_rt_cls.objects.filter.return_value.first.return_value = stolen
        from apps.accounts.services.auth_service import rotate_refresh_token
        result = rotate_refresh_token(str(uuid.uuid4()))
        assert result is None
        mock_revoke_all.assert_called_once_with(user)

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_new_pair_has_all_fields(self, mock_rt_cls):
        user = make_mock_user()
        type(user).is_superuser = PropertyMock(return_value=False)
        old_refresh = MagicMock()
        old_refresh.is_revoked = False
        old_refresh.expires_at = timezone.now() + timedelta(days=1)
        old_refresh.user = user
        old_refresh.user.pk = user.pk
        mock_rt_cls.objects.filter.return_value.first.return_value = old_refresh
        mock_rt_cls.objects.filter.return_value.update.return_value = 1
        mock_rt_cls.objects.create.return_value = MagicMock(token=str(uuid.uuid4()))
        from apps.accounts.services.auth_service import rotate_refresh_token
        result = rotate_refresh_token(str(uuid.uuid4()))
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "Bearer"

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_rotate_returns_none_if_race_condition(self, mock_rt_cls):
        user = make_mock_user()
        old_refresh = MagicMock()
        old_refresh.is_revoked = False
        old_refresh.expires_at = timezone.now() + timedelta(days=1)
        old_refresh.user = user
        old_refresh.user.pk = user.pk
        mock_rt_cls.objects.filter.return_value.first.return_value = old_refresh
        mock_rt_cls.objects.filter.return_value.update.return_value = 0  # race condition
        from apps.accounts.services.auth_service import rotate_refresh_token
        result = rotate_refresh_token(str(uuid.uuid4()))
        assert result is None

    @patch(f"{_AUTH_SVC}.revoke_all_sessions")
    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_stolen_token_returns_none(self, mock_rt_cls, mock_revoke_all):
        user = make_mock_user()
        stolen = MagicMock()
        stolen.is_revoked = True
        stolen.user = user
        mock_rt_cls.objects.filter.return_value.first.return_value = stolen
        from apps.accounts.services.auth_service import rotate_refresh_token
        result = rotate_refresh_token(str(uuid.uuid4()))
        assert result is None


# ---------------------------------------------------------------------------
# TestRevokeRefreshToken
# ---------------------------------------------------------------------------

class TestRevokeRefreshToken:

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_valid_token_revokes_and_returns_true(self, mock_rt_cls):
        user = make_mock_user()
        refresh = MagicMock()
        refresh.user = user
        refresh.user.pk = user.pk
        mock_rt_cls.objects.filter.return_value.first.return_value = refresh
        mock_rt_cls.objects.filter.return_value.update.return_value = 1
        from apps.accounts.services.auth_service import revoke_refresh_token
        result = revoke_refresh_token(str(uuid.uuid4()))
        assert result is True

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_invalid_token_returns_false(self, mock_rt_cls):
        mock_rt_cls.objects.filter.return_value.first.return_value = None
        from apps.accounts.services.auth_service import revoke_refresh_token
        result = revoke_refresh_token(str(uuid.uuid4()))
        assert result is False

    @patch(f"{_AUTH_SVC}.revoke_all_sessions")
    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_calls_revoke_all_sessions(self, mock_rt_cls, mock_revoke_all):
        user = make_mock_user()
        refresh = MagicMock()
        refresh.user = user
        mock_rt_cls.objects.filter.return_value.first.return_value = refresh
        from apps.accounts.services.auth_service import revoke_refresh_token
        revoke_refresh_token(str(uuid.uuid4()))
        mock_revoke_all.assert_called_once_with(user)

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_non_existent_token_returns_false(self, mock_rt_cls):
        mock_rt_cls.objects.filter.return_value.first.return_value = None
        from apps.accounts.services.auth_service import revoke_refresh_token
        result = revoke_refresh_token("00000000-0000-0000-0000-000000000000")
        assert result is False

    @patch(f"{_AUTH_SVC}.RefreshToken")
    def test_already_revoked_token_returns_false(self, mock_rt_cls):
        # filter(token=..., is_revoked=False) returns nothing when already revoked
        mock_rt_cls.objects.filter.return_value.first.return_value = None
        from apps.accounts.services.auth_service import revoke_refresh_token
        result = revoke_refresh_token(str(uuid.uuid4()))
        assert result is False


# ---------------------------------------------------------------------------
# TestGetUserInfo
# ---------------------------------------------------------------------------

class TestGetUserInfo:

    @patch(f"{_AUTH_SVC}.get_roles_and_permissions", return_value=(["admin"], ["PERM_A"]))
    @patch(f"{_AUTH_SVC}.User")
    def test_valid_token_returns_user_info(self, mock_user_cls, mock_rp):
        user = make_mock_user(id=42)
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_user_cls.objects.filter.return_value.first.return_value = user
        token = make_access_token(user_id=42)
        from apps.accounts.services.auth_service import get_user_info
        result = get_user_info(token)
        assert result is not None
        assert result["id"] == 42

    def test_invalid_token_returns_none(self):
        from apps.accounts.services.auth_service import get_user_info
        assert get_user_info("not.a.valid.jwt") is None

    def test_expired_token_returns_none(self):
        token = make_access_token(user_id=1, expired=True)
        from apps.accounts.services.auth_service import get_user_info
        assert get_user_info(token) is None

    @patch(f"{_AUTH_SVC}.User")
    def test_deleted_user_returns_none(self, mock_user_cls):
        user = make_mock_user()
        type(user).is_deleted = PropertyMock(return_value=True)
        mock_user_cls.objects.filter.return_value.first.return_value = user
        from apps.accounts.services.auth_service import get_user_info
        assert get_user_info(make_access_token(user_id=1)) is None

    @patch(f"{_AUTH_SVC}.User")
    def test_inactive_user_returns_none(self, mock_user_cls):
        user = make_mock_user(status="inactive")
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_user_cls.objects.filter.return_value.first.return_value = user
        from apps.accounts.services.auth_service import get_user_info
        assert get_user_info(make_access_token(user_id=1)) is None

    @patch(f"{_AUTH_SVC}.User")
    def test_user_not_found_returns_none(self, mock_user_cls):
        mock_user_cls.objects.filter.return_value.first.return_value = None
        from apps.accounts.services.auth_service import get_user_info
        assert get_user_info(make_access_token(user_id=999)) is None

    @patch(f"{_AUTH_SVC}.get_roles_and_permissions", return_value=(["admin"], ["PERM_A"]))
    @patch(f"{_AUTH_SVC}.User")
    def test_result_contains_all_fields(self, mock_user_cls, mock_rp):
        user = make_mock_user(id=5)
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_user_cls.objects.filter.return_value.first.return_value = user
        from apps.accounts.services.auth_service import get_user_info
        result = get_user_info(make_access_token(user_id=5))
        for field in ("id", "email", "username", "name", "roles", "permissions"):
            assert field in result

    @patch(f"{_AUTH_SVC}.get_roles_and_permissions", return_value=(["editor"], ["POST_EDIT"]))
    @patch(f"{_AUTH_SVC}.User")
    def test_result_roles_and_permissions_included(self, mock_user_cls, mock_rp):
        user = make_mock_user(id=5)
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_user_cls.objects.filter.return_value.first.return_value = user
        from apps.accounts.services.auth_service import get_user_info
        result = get_user_info(make_access_token(user_id=5))
        assert "editor" in result["roles"]
        assert "POST_EDIT" in result["permissions"]

    @patch(f"{_AUTH_SVC}.User")
    def test_force_logout_blocks_old_token(self, mock_user_cls):
        """Tokens emitidos antes de tokens_valid_after deben ser rechazados."""
        import jwt as pyjwt
        from django.conf import settings
        past_iat = int((timezone.now() - timedelta(hours=2)).timestamp())
        exp = int((timezone.now() + timedelta(hours=1)).timestamp())
        payload = {"user_id": 10, "is_super_admin": False, "exp": exp, "iat": past_iat}
        token = pyjwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm=settings.JWT_ALGORITHM)
        user = make_mock_user(id=10)
        type(user).is_deleted = PropertyMock(return_value=False)
        user.tokens_valid_after = timezone.now() - timedelta(hours=1)
        mock_user_cls.objects.filter.return_value.first.return_value = user
        from apps.accounts.services.auth_service import get_user_info
        assert get_user_info(token) is None


# ---------------------------------------------------------------------------
# TestIntrospectToken
# ---------------------------------------------------------------------------

class TestIntrospectToken:

    @patch(f"{_AUTH_SVC}.get_roles_and_permissions", return_value=([], []))
    @patch(f"{_AUTH_SVC}.User")
    def test_valid_token_returns_payload(self, mock_user_cls, mock_rp):
        user = make_mock_user(id=5)
        type(user).is_deleted = PropertyMock(return_value=False)
        type(user).is_superuser = PropertyMock(return_value=False)
        mock_user_cls.objects.filter.return_value.first.return_value = user
        token = make_access_token(user_id=5)
        from apps.accounts.services.auth_service import introspect_token
        result = introspect_token(token)
        assert result is not None
        assert result["user_id"] == 5

    def test_invalid_token_returns_none(self):
        from apps.accounts.services.auth_service import introspect_token
        assert introspect_token("garbage") is None

    def test_expired_token_returns_none(self):
        token = make_access_token(user_id=1, expired=True)
        from apps.accounts.services.auth_service import introspect_token
        assert introspect_token(token) is None

    @patch(f"{_AUTH_SVC}.User")
    def test_user_not_found_returns_none(self, mock_user_cls):
        mock_user_cls.objects.filter.return_value.first.return_value = None
        from apps.accounts.services.auth_service import introspect_token
        assert introspect_token(make_access_token(user_id=404)) is None

    @patch(f"{_AUTH_SVC}.get_roles_and_permissions", return_value=(["admin"], ["PERM_A"]))
    @patch(f"{_AUTH_SVC}.User")
    def test_result_has_user_id(self, mock_user_cls, mock_rp):
        user = make_mock_user(id=7)
        type(user).is_deleted = PropertyMock(return_value=False)
        type(user).is_superuser = PropertyMock(return_value=False)
        mock_user_cls.objects.filter.return_value.first.return_value = user
        from apps.accounts.services.auth_service import introspect_token
        result = introspect_token(make_access_token(user_id=7))
        assert result["user_id"] == 7

    @patch(f"{_AUTH_SVC}.get_roles_and_permissions", return_value=([], []))
    @patch(f"{_AUTH_SVC}.User")
    def test_result_has_is_super_admin(self, mock_user_cls, mock_rp):
        user = make_mock_user(id=7)
        type(user).is_deleted = PropertyMock(return_value=False)
        type(user).is_superuser = PropertyMock(return_value=True)
        mock_user_cls.objects.filter.return_value.first.return_value = user
        from apps.accounts.services.auth_service import introspect_token
        result = introspect_token(make_access_token(user_id=7))
        assert "is_super_admin" in result

    @patch(f"{_AUTH_SVC}.get_roles_and_permissions", return_value=(["r1"], ["P1"]))
    @patch(f"{_AUTH_SVC}.User")
    def test_result_has_roles_and_permissions(self, mock_user_cls, mock_rp):
        user = make_mock_user(id=7)
        type(user).is_deleted = PropertyMock(return_value=False)
        type(user).is_superuser = PropertyMock(return_value=False)
        mock_user_cls.objects.filter.return_value.first.return_value = user
        from apps.accounts.services.auth_service import introspect_token
        result = introspect_token(make_access_token(user_id=7))
        assert "roles" in result
        assert "permissions" in result

    @patch(f"{_AUTH_SVC}.get_roles_and_permissions", return_value=([], []))
    @patch(f"{_AUTH_SVC}.User")
    def test_result_has_four_keys(self, mock_user_cls, mock_rp):
        user = make_mock_user(id=7)
        type(user).is_deleted = PropertyMock(return_value=False)
        type(user).is_superuser = PropertyMock(return_value=False)
        mock_user_cls.objects.filter.return_value.first.return_value = user
        from apps.accounts.services.auth_service import introspect_token
        result = introspect_token(make_access_token(user_id=7))
        assert set(result.keys()) == {"user_id", "roles", "permissions", "is_super_admin"}
