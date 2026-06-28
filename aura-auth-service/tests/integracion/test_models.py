import pytest
from django.utils import timezone

from apps.accounts.models import User, Role, Permission, UserRole, PermissionInRole, RefreshToken
from apps.accounts.utils import get_user_permissions, get_user_roles, user_has_permission

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# TestUserModel
# ---------------------------------------------------------------------------

class TestUserModel:

    def test_create_user(self, bootstrap_user):
        user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="pass123",
            created_by=bootstrap_user,
        )
        assert user.username == "alice"
        assert user.email == "alice@example.com"
        assert user.status == "active"
        assert user.created_by == bootstrap_user

    def test_user_has_int_pk(self, regular_user):
        assert isinstance(regular_user.id, int)

    def test_username_uniqueness(self, bootstrap_user):
        User.objects.create_user("unique1", "unique1@example.com", "pass", created_by=bootstrap_user)
        with pytest.raises(Exception):
            User.objects.create_user("unique1", "other@example.com", "pass", created_by=bootstrap_user)

    def test_email_uniqueness(self, bootstrap_user):
        User.objects.create_user("unique2", "dup@example.com", "pass", created_by=bootstrap_user)
        with pytest.raises(Exception):
            User.objects.create_user("unique3", "dup@example.com", "pass", created_by=bootstrap_user)

    def test_password_hashing(self, regular_user):
        assert regular_user.password != "testpass123"
        assert regular_user.check_password("testpass123")

    def test_set_password(self, regular_user):
        regular_user.set_password("newpass456")
        regular_user.save()
        assert regular_user.check_password("newpass456")
        assert not regular_user.check_password("testpass123")

    def test_soft_delete(self, regular_user, bootstrap_user):
        assert regular_user.deleted_at is None
        assert not regular_user.is_deleted
        regular_user.soft_delete(deleted_by=bootstrap_user)
        assert regular_user.deleted_at is not None
        assert regular_user.is_deleted
        assert regular_user.deleted_by == bootstrap_user

    def test_restore(self, regular_user, bootstrap_user):
        regular_user.soft_delete(deleted_by=bootstrap_user)
        regular_user.restore()
        assert regular_user.deleted_at is None
        assert not regular_user.is_deleted

    def test_create_superuser_assigns_role(self, bootstrap_user):
        assert bootstrap_user.is_superuser

    def test_is_deleted_property_false_for_active(self, regular_user):
        assert regular_user.is_deleted is False

    def test_force_logout_at_none_on_creation(self, regular_user):
        assert regular_user.force_logout_at is None

    def test_created_by_field_persists(self, regular_user, bootstrap_user):
        regular_user.refresh_from_db()
        assert regular_user.created_by == bootstrap_user


# ---------------------------------------------------------------------------
# TestRoleModel
# ---------------------------------------------------------------------------

class TestRoleModel:

    def test_create_role(self):
        role = Role.objects.create(name="editor", description="Editor role")
        assert role.name == "editor"
        assert role.description == "Editor role"

    def test_role_has_int_pk(self):
        role = Role.objects.create(name="viewer", description="")
        assert isinstance(role.id, int)

    def test_role_name_persists(self):
        role = Role.objects.create(name="manager", description="")
        fetched = Role.objects.get(pk=role.pk)
        assert fetched.name == "manager"

    def test_role_description_can_be_empty(self):
        role = Role.objects.create(name="noroles", description="")
        assert role.description == ""


# ---------------------------------------------------------------------------
# TestPermissionModel
# ---------------------------------------------------------------------------

class TestPermissionModel:

    def test_create_permission(self):
        perm = Permission.objects.create(name="user.create", description="Create users")
        assert perm.name == "user.create"

    def test_permission_has_int_pk(self):
        perm = Permission.objects.create(name="user.read")
        assert isinstance(perm.id, int)

    def test_permission_name_persists(self):
        perm = Permission.objects.create(name="post.publish")
        fetched = Permission.objects.get(pk=perm.pk)
        assert fetched.name == "post.publish"


# ---------------------------------------------------------------------------
# TestPermissionUtils
# ---------------------------------------------------------------------------

class TestPermissionUtils:

    def test_user_permissions_flow(self, bootstrap_user, regular_user):
        role = Role.objects.create(name="writer", description="")
        perm = Permission.objects.create(name="post.write")
        UserRole.objects.create(user=regular_user, role=role, created_by=bootstrap_user)
        PermissionInRole.objects.create(role=role, permission=perm)
        assert user_has_permission(regular_user, "post.write")
        assert "POST_WRITE" in get_user_permissions(regular_user)
        assert "writer" in get_user_roles(regular_user)

    def test_superuser_has_all_permissions(self, bootstrap_user):
        Permission.objects.create(name="admin.access")
        assert user_has_permission(bootstrap_user, "admin.access")

    def test_user_without_roles_has_no_permissions(self, regular_user):
        assert get_user_permissions(regular_user) == []

    def test_get_user_roles_returns_role_name(self, bootstrap_user, regular_user):
        role = Role.objects.create(name="reporter", description="")
        UserRole.objects.create(user=regular_user, role=role, created_by=bootstrap_user)
        roles = get_user_roles(regular_user)
        assert "reporter" in roles


# ---------------------------------------------------------------------------
# TestRefreshToken
# ---------------------------------------------------------------------------

class TestRefreshToken:

    def test_create_refresh_token_persists(self, regular_user):
        from datetime import timedelta
        token = RefreshToken.objects.create(
            token="test-token-123",
            user=regular_user,
            expires_at=timezone.now() + timedelta(days=7),
            created_by=regular_user.pk,
            updated_by=regular_user.pk,
        )
        assert RefreshToken.objects.filter(id=token.id).exists()

    def test_is_revoked_defaults_to_false(self, regular_user):
        from datetime import timedelta
        token = RefreshToken.objects.create(
            token="test-token-456",
            user=regular_user,
            expires_at=timezone.now() + timedelta(days=7),
            created_by=regular_user.pk,
            updated_by=regular_user.pk,
        )
        assert token.is_revoked is False

    def test_expires_at_in_future(self, regular_user):
        from datetime import timedelta
        token = RefreshToken.objects.create(
            token="test-token-789",
            user=regular_user,
            expires_at=timezone.now() + timedelta(days=7),
            created_by=regular_user.pk,
            updated_by=regular_user.pk,
        )
        assert token.expires_at > timezone.now()

    def test_token_user_fk_correct(self, regular_user):
        from datetime import timedelta
        token = RefreshToken.objects.create(
            token="test-token-abc",
            user=regular_user,
            expires_at=timezone.now() + timedelta(days=7),
            created_by=regular_user.pk,
            updated_by=regular_user.pk,
        )
        assert token.user_id == regular_user.pk

    def test_token_value_is_unique(self, regular_user):
        from datetime import timedelta
        RefreshToken.objects.create(
            token="unique-token-xyz",
            user=regular_user,
            expires_at=timezone.now() + timedelta(days=7),
            created_by=regular_user.pk,
            updated_by=regular_user.pk,
        )
        with pytest.raises(Exception):
            RefreshToken.objects.create(
                token="unique-token-xyz",
                user=regular_user,
                expires_at=timezone.now() + timedelta(days=7),
                created_by=regular_user.pk,
                updated_by=regular_user.pk,
            )
