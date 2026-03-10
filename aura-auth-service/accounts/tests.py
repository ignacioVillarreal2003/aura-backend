"""
Tests for accounts models.

This module contains basic tests for User, Role, and Permission models.
Run with: python manage.py test accounts
"""

from django.test import TestCase
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from accounts.models import User, Role, Permission, UserRole, RolePermission
from accounts.utils import (
    assign_role_to_user,
    assign_permission_to_role,
    user_has_permission,
    user_has_role,
    get_user_permissions,
    get_user_roles,
)


class UserModelTest(TestCase):
    """Test custom User model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_user(self):
        """Test user creation."""
        self.assertEqual(self.user.username, 'testuser')
        self.assertEqual(self.user.email, 'test@example.com')
        self.assertTrue(self.user.is_active)
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)

    def test_user_has_uuid_pk(self):
        """Test user has UUID primary key."""
        self.assertIsNotNone(self.user.id)
        self.assertEqual(len(str(self.user.id)), 36)  # UUID format

    def test_username_uniqueness(self):
        """Test username must be unique."""
        with self.assertRaises(Exception):
            User.objects.create_user(
                username='testuser',
                email='other@example.com',
                password='pass'
            )

    def test_email_uniqueness(self):
        """Test email must be unique."""
        with self.assertRaises(Exception):
            User.objects.create_user(
                username='other',
                email='test@example.com',
                password='pass'
            )

    def test_password_hashing(self):
        """Test password is hashed, not stored in plain text."""
        self.assertNotEqual(self.user.password_hash, 'testpass123')
        self.assertTrue(self.user.check_password('testpass123'))

    def test_set_password(self):
        """Test set_password method."""
        self.user.set_password('newpass123')
        self.assertTrue(self.user.check_password('newpass123'))
        self.assertFalse(self.user.check_password('testpass123'))

    def test_soft_delete(self):
        """Test soft delete functionality."""
        self.assertIsNone(self.user.deleted_at)
        self.assertFalse(self.user.is_deleted)

        self.user.soft_delete(deleted_by='admin')

        self.assertIsNotNone(self.user.deleted_at)
        self.assertTrue(self.user.is_deleted)
        self.assertEqual(self.user.deleted_by, 'admin')

    def test_restore(self):
        """Test restore soft-deleted user."""
        self.user.soft_delete(deleted_by='admin')
        self.user.restore()

        self.assertIsNone(self.user.deleted_at)
        self.assertFalse(self.user.is_deleted)

    def test_soft_delete_filtered_query(self):
        """Test soft-deleted users excluded from default queries."""
        count_before = User.objects.filter(deleted_at__isnull=True).count()
        self.user.soft_delete()
        count_after = User.objects.filter(deleted_at__isnull=True).count()

        self.assertEqual(count_before - 1, count_after)

    def test_create_superuser(self):
        """Test superuser creation."""
        superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass'
        )

        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_active)

    def test_audit_fields(self):
        """Test audit fields are set."""
        self.assertIsNotNone(self.user.created_at)
        self.assertIsNotNone(self.user.updated_at)
        self.assertIsNone(self.user.created_by)
        self.assertIsNone(self.user.updated_by)


class RoleModelTest(TestCase):
    """Test Role model."""

    def setUp(self):
        """Set up test data."""
        self.role = Role.objects.create(
            name='ADMIN',
            description='Administrator role'
        )

    def test_create_role(self):
        """Test role creation."""
        self.assertEqual(self.role.name, 'ADMIN')
        self.assertEqual(self.role.description, 'Administrator role')

    def test_role_has_uuid_pk(self):
        """Test role has UUID primary key."""
        self.assertIsNotNone(self.role.id)

    def test_role_name_uniqueness(self):
        """Test role name must be unique."""
        with self.assertRaises(Exception):
            Role.objects.create(
                name='ADMIN',
                description='Another admin role'
            )

    def test_soft_delete(self):
        """Test soft delete for role."""
        self.role.soft_delete(deleted_by='admin')
        self.assertTrue(self.role.is_deleted)


class PermissionModelTest(TestCase):
    """Test Permission model."""

    def setUp(self):
        """Set up test data."""
        self.permission = Permission.objects.create(
            code='user.create',
            description='Create new users'
        )

    def test_create_permission(self):
        """Test permission creation."""
        self.assertEqual(self.permission.code, 'user.create')

    def test_permission_code_uniqueness(self):
        """Test permission code must be unique."""
        with self.assertRaises(Exception):
            Permission.objects.create(
                code='user.create',
                description='Other description'
            )


class UserRoleRelationshipTest(TestCase):
    """Test User-Role relationships."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='john',
            email='john@example.com',
            password='pass'
        )
        self.role = Role.objects.create(name='MANAGER')

    def test_assign_role_to_user(self):
        """Test assigning role to user."""
        user_role = assign_role_to_user(self.user, self.role, assigned_by='admin')

        self.assertEqual(user_role.user, self.user)
        self.assertEqual(user_role.role, self.role)
        self.assertEqual(user_role.assigned_by, 'admin')

    def test_user_has_role(self):
        """Test checking if user has role."""
        assign_role_to_user(self.user, self.role)

        self.assertTrue(user_has_role(self.user, 'MANAGER'))
        self.assertFalse(user_has_role(self.user, 'USER'))

    def test_unique_constraint(self):
        """Test user cannot have duplicate role."""
        UserRole.objects.create(user=self.user, role=self.role)

        with self.assertRaises(Exception):
            UserRole.objects.create(user=self.user, role=self.role)


class RolePermissionRelationshipTest(TestCase):
    """Test Role-Permission relationships."""

    def setUp(self):
        """Set up test data."""
        self.role = Role.objects.create(name='VIEWER')
        self.permission = Permission.objects.create(code='user.read')

    def test_assign_permission_to_role(self):
        """Test assigning permission to role."""
        role_perm = assign_permission_to_role(
            self.role,
            self.permission,
            granted_by='admin'
        )

        self.assertEqual(role_perm.role, self.role)
        self.assertEqual(role_perm.permission, self.permission)
        self.assertEqual(role_perm.granted_by, 'admin')

    def test_unique_constraint(self):
        """Test role cannot have duplicate permission."""
        RolePermission.objects.create(role=self.role, permission=self.permission)

        with self.assertRaises(Exception):
            RolePermission.objects.create(role=self.role, permission=self.permission)


class UtilityFunctionsTest(TestCase):
    """Test utility functions."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='pass'
        )
        self.role = Role.objects.create(name='EDITOR')
        self.perm1 = Permission.objects.create(code='post.create')
        self.perm2 = Permission.objects.create(code='post.edit')
        self.perm3 = Permission.objects.create(code='post.delete')

    def test_user_has_permission(self):
        """Test user_has_permission utility."""
        # User doesn't have permission yet
        self.assertFalse(user_has_permission(self.user, 'post.create'))

        # Assign role with permission
        assign_role_to_user(self.user, self.role)
        assign_permission_to_role(self.role, self.perm1)

        # Now user has permission
        self.assertTrue(user_has_permission(self.user, 'post.create'))
        self.assertFalse(user_has_permission(self.user, 'post.delete'))

    def test_get_user_permissions(self):
        """Test get_user_permissions utility."""
        assign_role_to_user(self.user, self.role)
        assign_permission_to_role(self.role, self.perm1)
        assign_permission_to_role(self.role, self.perm2)

        permissions = get_user_permissions(self.user)

        self.assertIn('post.create', permissions)
        self.assertIn('post.edit', permissions)
        self.assertNotIn('post.delete', permissions)

    def test_get_user_roles(self):
        """Test get_user_roles utility."""
        assign_role_to_user(self.user, self.role)

        roles = get_user_roles(self.user)

        self.assertEqual(len(roles), 1)

    def test_superuser_has_all_permissions(self):
        """Test superuser automatically has all permissions."""
        superuser = User.objects.create_superuser(
            username='super',
            email='super@example.com',
            password='pass'
        )

        # Superuser has permission even if not assigned
        self.assertTrue(user_has_permission(superuser, 'post.create'))
        self.assertTrue(user_has_permission(superuser, 'post.delete'))
        self.assertTrue(user_has_permission(superuser, 'any.permission'))
