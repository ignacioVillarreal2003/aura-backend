from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from apps.accounts.utils import (
    _normalize_permission_name,
    get_user_permissions,
    get_user_roles,
    user_has_permission,
)
from apps.accounts.models import User


def _make_mock_user(is_superuser=False):
    user = MagicMock(spec=User)
    type(user).is_superuser = PropertyMock(return_value=is_superuser)
    return user


# ---------------------------------------------------------------------------
# TestNormalizePermissionName
# ---------------------------------------------------------------------------

class TestNormalizePermissionName:

    def test_dot_becomes_underscore(self):
        assert _normalize_permission_name("post.edit") == "POST_EDIT"

    def test_lowercased_becomes_uppercase(self):
        assert _normalize_permission_name("user_read") == "USER_READ"

    def test_empty_string_returns_empty(self):
        assert _normalize_permission_name("") == ""

    def test_none_returns_empty(self):
        assert _normalize_permission_name(None) == ""

    def test_mixed_case_dots(self):
        assert _normalize_permission_name("Admin.Users.View") == "ADMIN_USERS_VIEW"


# ---------------------------------------------------------------------------
# TestGetUserPermissions
# ---------------------------------------------------------------------------

class TestGetUserPermissions:

    def test_returns_list(self):
        user = _make_mock_user()
        qs = MagicMock()
        qs.filter.return_value.values_list.return_value = ["post.edit"]
        user.user_roles = qs
        result = get_user_permissions(user)
        assert isinstance(result, list)

    def test_normalizes_dot_to_underscore_uppercase(self):
        user = _make_mock_user()
        qs = MagicMock()
        qs.filter.return_value.values_list.return_value = ["post.edit"]
        user.user_roles = qs
        result = get_user_permissions(user)
        assert "POST_EDIT" in result

    @patch("apps.accounts.utils.Permission")
    def test_superuser_gets_all_permissions(self, mock_permission_cls):
        user = _make_mock_user(is_superuser=True)
        mock_permission_cls.objects.values_list.return_value = ["user.read", "user.create"]
        result = get_user_permissions(user)
        assert "USER_READ" in result
        assert "USER_CREATE" in result

    def test_user_without_roles_returns_empty(self):
        user = _make_mock_user()
        qs = MagicMock()
        qs.filter.return_value.values_list.return_value = []
        user.user_roles = qs
        result = get_user_permissions(user)
        assert result == []

    def test_ignores_none_values(self):
        user = _make_mock_user()
        qs = MagicMock()
        qs.filter.return_value.values_list.return_value = [None, "post.edit"]
        user.user_roles = qs
        result = get_user_permissions(user)
        assert None not in result
        assert "POST_EDIT" in result


# ---------------------------------------------------------------------------
# TestGetUserRoles
# ---------------------------------------------------------------------------

class TestGetUserRoles:

    def test_returns_role_names(self):
        user = _make_mock_user()
        qs = MagicMock()
        qs.filter.return_value.values_list.return_value = ["Admin"]
        user.user_roles = qs
        result = get_user_roles(user)
        assert "admin" in result

    def test_roles_are_lowercased(self):
        user = _make_mock_user()
        qs = MagicMock()
        qs.filter.return_value.values_list.return_value = ["EDITOR"]
        user.user_roles = qs
        result = get_user_roles(user)
        assert "editor" in result

    def test_user_without_roles_returns_empty(self):
        user = _make_mock_user()
        qs = MagicMock()
        qs.filter.return_value.values_list.return_value = []
        user.user_roles = qs
        result = get_user_roles(user)
        assert result == []

    def test_ignores_none_values(self):
        user = _make_mock_user()
        qs = MagicMock()
        qs.filter.return_value.values_list.return_value = [None, "viewer"]
        user.user_roles = qs
        result = get_user_roles(user)
        assert None not in result


# ---------------------------------------------------------------------------
# TestUserHasPermission
# ---------------------------------------------------------------------------

class TestUserHasPermission:

    def test_returns_true_with_permission(self):
        user = _make_mock_user()
        with patch("apps.accounts.utils.get_user_permissions", return_value=["POST_EDIT"]):
            assert user_has_permission(user, "post.edit") is True

    def test_returns_false_without_permission(self):
        user = _make_mock_user()
        with patch("apps.accounts.utils.get_user_permissions", return_value=[]):
            assert user_has_permission(user, "post.edit") is False

    def test_superuser_always_has_permission(self):
        user = _make_mock_user(is_superuser=True)
        assert user_has_permission(user, "any.permission") is True

    def test_dot_to_underscore_normalization(self):
        user = _make_mock_user()
        with patch("apps.accounts.utils.get_user_permissions", return_value=["USER_CREATE"]):
            assert user_has_permission(user, "user.create") is True

    def test_case_insensitive_normalization(self):
        user = _make_mock_user()
        with patch("apps.accounts.utils.get_user_permissions", return_value=["USER_READ"]):
            assert user_has_permission(user, "User.Read") is True
