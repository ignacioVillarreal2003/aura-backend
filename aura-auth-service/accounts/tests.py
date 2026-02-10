"""
Tests for accounts models.

Run with: python manage.py test accounts
"""

from django.test import TestCase
from accounts.models import User, Role, Permission, UserRole, PermissionInRole
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
        self.bootstrap_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass',
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            created_by=self.bootstrap_user,
        )

    def test_create_user(self):
        self.assertEqual(self.user.username, 'testuser')
        self.assertEqual(self.user.email, 'test@example.com')
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.user.status, 'active')
        self.assertEqual(self.user.created_by, self.bootstrap_user)

    def test_user_has_int_pk(self):
        self.assertIsInstance(self.user.id, int)

    def test_username_uniqueness(self):
        with self.assertRaises(Exception):
            User.objects.create_user(
                username='testuser',
                email='other@example.com',
                password='pass',
                created_by=self.bootstrap_user,
            )

    def test_email_uniqueness(self):
        with self.assertRaises(Exception):
            User.objects.create_user(
                username='other',
                email='test@example.com',
                password='pass',
                created_by=self.bootstrap_user,
            )

    def test_password_hashing(self):
        self.assertNotEqual(self.user.password, 'testpass123')
        self.assertTrue(self.user.check_password('testpass123'))

    def test_set_password(self):
        self.user.set_password('newpass123')
        self.user.save()
        self.assertTrue(self.user.check_password('newpass123'))
        self.assertFalse(self.user.check_password('testpass123'))

    def test_soft_delete(self):
        self.assertIsNone(self.user.deleted_at)
        self.assertFalse(self.user.is_deleted)

        self.user.soft_delete(deleted_by=self.bootstrap_user)

        self.assertIsNotNone(self.user.deleted_at)
        self.assertTrue(self.user.is_deleted)
        self.assertEqual(self.user.deleted_by, self.bootstrap_user)

    def test_restore(self):
        self.user.soft_delete(deleted_by=self.bootstrap_user)
        self.user.restore()

        self.assertIsNone(self.user.deleted_at)
        self.assertFalse(self.user.is_deleted)

    def test_create_superuser_assigns_role(self):
        self.assertTrue(self.bootstrap_user.is_superuser)


class RoleModelTest(TestCase):
    """Test Role model."""

    def setUp(self):
        self.role = Role.objects.create(
            name='ADMIN',
            description='Administrator role',
        )

    def test_create_role(self):
        self.assertEqual(self.role.name, 'ADMIN')
        self.assertEqual(self.role.description, 'Administrator role')

    def test_role_has_int_pk(self):
        self.assertIsInstance(self.role.id, int)


class PermissionModelTest(TestCase):
    """Test Permission model."""

    def setUp(self):
        self.permission = Permission.objects.create(
            name='user.create',
            description='Create new users',
        )

    def test_create_permission(self):
        self.assertEqual(self.permission.name, 'user.create')


class UserRoleRelationshipTest(TestCase):
    """Test User-Role relationships."""

    def setUp(self):
        self.bootstrap_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass',
        )
        self.user = User.objects.create_user(
            username='john',
            email='john@example.com',
            password='pass',
            created_by=self.bootstrap_user,
        )
        self.role = Role.objects.create(name='MANAGER', description='Manager role')

    def test_assign_role_to_user(self):
        user_role = assign_role_to_user(self.user, self.role, created_by=self.bootstrap_user)

        self.assertEqual(user_role.user, self.user)
        self.assertEqual(user_role.role, self.role)
        self.assertEqual(user_role.created_by, self.bootstrap_user)

    def test_user_has_role(self):
        assign_role_to_user(self.user, self.role, created_by=self.bootstrap_user)

        self.assertTrue(user_has_role(self.user, 'MANAGER'))
        self.assertFalse(user_has_role(self.user, 'USER'))


class PermissionInRoleRelationshipTest(TestCase):
    """Test Role-Permission relationships."""

    def setUp(self):
        self.role = Role.objects.create(name='VIEWER', description='Viewer role')
        self.permission = Permission.objects.create(name='user.read')

    def test_assign_permission_to_role(self):
        role_perm = assign_permission_to_role(self.role, self.permission)
        self.assertEqual(role_perm.role, self.role)
        self.assertEqual(role_perm.permission, self.permission)


class PermissionUtilsTest(TestCase):
    def setUp(self):
        self.bootstrap_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass',
        )
        self.user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='pass',
            created_by=self.bootstrap_user,
        )
        self.role = Role.objects.create(name='EDITOR', description='Editor role')
        self.permission = Permission.objects.create(name='post.edit')

    def test_user_permissions_flow(self):
        assign_role_to_user(self.user, self.role, created_by=self.bootstrap_user)
        assign_permission_to_role(self.role, self.permission)

        self.assertTrue(user_has_permission(self.user, 'post.edit'))
        self.assertIn('post.edit', get_user_permissions(self.user))
        self.assertIn('EDITOR', get_user_roles(self.user))
