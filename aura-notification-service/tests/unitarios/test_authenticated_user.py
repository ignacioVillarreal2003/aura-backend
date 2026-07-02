import pytest
from core.authentication.authenticated_user import AuthenticatedUser


def make_user(**kwargs):
    defaults = dict(id=1, email="test@test.com", username="testuser")
    defaults.update(kwargs)
    return AuthenticatedUser(**defaults)


class TestAuthenticatedUser:
    def test_is_authenticated_always_true(self):
        user = make_user()
        assert user.is_authenticated is True

    def test_pk_equals_id(self):
        user = make_user(id=42)
        assert user.pk == 42

    def test_has_all_permissions_exact_match(self):
        user = make_user(permissions=("read", "write"))
        assert user.has_all_permissions(frozenset({"read", "write"})) is True

    def test_has_all_permissions_with_superset(self):
        user = make_user(permissions=("read", "write", "delete"))
        assert user.has_all_permissions(frozenset({"read"})) is True

    def test_has_all_permissions_false_when_missing_one(self):
        user = make_user(permissions=("read",))
        assert user.has_all_permissions(frozenset({"read", "write"})) is False

    def test_has_all_permissions_empty_required_true(self):
        user = make_user(permissions=())
        assert user.has_all_permissions(frozenset()) is True

    def test_has_any_role_true_on_match(self):
        user = make_user(roles=("admin", "viewer"))
        assert user.has_any_role(frozenset({"admin"})) is True

    def test_has_any_role_false_on_no_match(self):
        user = make_user(roles=("viewer",))
        assert user.has_any_role(frozenset({"admin"})) is False

    def test_has_any_role_empty_set_false(self):
        user = make_user(roles=("admin",))
        assert user.has_any_role(frozenset()) is False
