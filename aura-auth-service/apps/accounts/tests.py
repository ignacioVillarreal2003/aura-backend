"""Tests de los modelos, vistas y servicios de accounts."""

import uuid
import jwt
from datetime import timedelta
from unittest.mock import patch, MagicMock, PropertyMock

from django.test import TestCase, RequestFactory
from django.utils import timezone
from django.conf import settings

from rest_framework.test import APIClient

from apps.accounts.models import User, Role, Permission, UserRole, PermissionInRole
from apps.accounts.utils import (
    user_has_permission,
    get_user_permissions,
    get_user_roles,
)



def _make_user(**kwargs):
    """Devuelve un MagicMock que parece un usuario, sin guardarlo."""
    user = MagicMock(spec=User)
    user.id = kwargs.get('id', 1)
    user.pk = user.id
    user.username = kwargs.get('username', 'testuser')
    user.email = kwargs.get('email', 'test@example.com')
    user.name = kwargs.get('name', 'Test User')
    user.status = kwargs.get('status', 'active')
    user.is_deleted = kwargs.get('is_deleted', False)
    user.deleted_at = None if not user.is_deleted else timezone.now()
    user.account_non_locked = kwargs.get('account_non_locked', True)
    user.lockout_until = kwargs.get('lockout_until', None)
    user.is_superuser = kwargs.get('is_superuser', False)
    return user


def _make_access_token(user_id=1, expired=False):
    """Arma un JWT real para usar en los tests."""
    if expired:
        exp = int((timezone.now() - timedelta(hours=1)).timestamp())
    else:
        exp = int((timezone.now() + timedelta(minutes=15)).timestamp())
    payload = {'user_id': user_id, 'is_super_admin': False, 'exp': exp}
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm=settings.JWT_ALGORITHM)



class UserModelTest(TestCase):
    """Tests del modelo User."""

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
    """Tests del modelo Role."""

    def setUp(self):
        self.role = Role.objects.create(
            name='admin',
            description='Administrator role',
        )

    def test_create_role(self):
        self.assertEqual(self.role.name, 'admin')
        self.assertEqual(self.role.description, 'Administrator role')

    def test_role_has_int_pk(self):
        self.assertIsInstance(self.role.id, int)


class PermissionModelTest(TestCase):
    """Tests del modelo Permission."""

    def setUp(self):
        self.permission = Permission.objects.create(
            name='user.create',
            description='Create new users',
        )

    def test_create_permission(self):
        self.assertEqual(self.permission.name, 'user.create')


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
        self.role = Role.objects.create(name='editor', description='Editor role')
        self.permission = Permission.objects.create(name='post.edit')

    def test_user_permissions_flow(self):
        UserRole.objects.create(user=self.user, role=self.role, created_by=self.bootstrap_user)
        PermissionInRole.objects.create(role=self.role, permission=self.permission)

        self.assertTrue(user_has_permission(self.user, 'post.edit'))
        self.assertIn('POST_EDIT', get_user_permissions(self.user))
        self.assertIn('editor', get_user_roles(self.user))



class AuthenticateUserTest(TestCase):
    """Tests de auth_service.authenticate_user."""

    @patch('apps.accounts.services.auth_service.authenticate')
    def test_valid_credentials_return_user(self, mock_auth):
        user = _make_user()
        mock_auth.return_value = user
        from apps.accounts.services.auth_service import authenticate_user
        result = authenticate_user('testuser', 'pass')
        self.assertEqual(result, user)

    @patch('apps.accounts.services.auth_service.authenticate')
    def test_invalid_credentials_return_none(self, mock_auth):
        mock_auth.return_value = None
        from apps.accounts.services.auth_service import authenticate_user
        result = authenticate_user('testuser', 'wrongpass')
        self.assertIsNone(result)

    @patch('apps.accounts.services.auth_service.authenticate')
    def test_deleted_user_returns_none(self, mock_auth):
        user = _make_user(is_deleted=True)
        type(user).is_deleted = PropertyMock(return_value=True)
        mock_auth.return_value = user
        from apps.accounts.services.auth_service import authenticate_user
        result = authenticate_user('testuser', 'pass')
        self.assertIsNone(result)

    @patch('apps.accounts.services.auth_service.authenticate')
    def test_inactive_user_returns_none(self, mock_auth):
        user = _make_user(status='inactive')
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_auth.return_value = user
        from apps.accounts.services.auth_service import authenticate_user
        result = authenticate_user('testuser', 'pass')
        self.assertIsNone(result)

    @patch('apps.accounts.services.auth_service.authenticate')
    def test_locked_account_returns_none(self, mock_auth):
        user = _make_user(account_non_locked=False)
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_auth.return_value = user
        from apps.accounts.services.auth_service import authenticate_user
        result = authenticate_user('testuser', 'pass')
        self.assertIsNone(result)

    @patch('apps.accounts.services.auth_service.authenticate')
    def test_lockout_until_future_returns_none(self, mock_auth):
        user = _make_user(lockout_until=timezone.now() + timedelta(minutes=10))
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_auth.return_value = user
        from apps.accounts.services.auth_service import authenticate_user
        result = authenticate_user('testuser', 'pass')
        self.assertIsNone(result)

    @patch('apps.accounts.services.auth_service.authenticate')
    def test_lockout_until_past_allows_login(self, mock_auth):
        """Un lockout_until en el pasado no debe bloquear al usuario."""
        user = _make_user(lockout_until=timezone.now() - timedelta(minutes=1))
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_auth.return_value = user
        from apps.accounts.services.auth_service import authenticate_user
        result = authenticate_user('testuser', 'pass')
        self.assertEqual(result, user)


class IssueTokensForUserTest(TestCase):
    """Tests de auth_service.issue_tokens_for_user."""

    def _mock_qs(self):
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.update.return_value = 1
        return qs

    @patch('apps.accounts.services.auth_service.RefreshToken')
    def test_returns_token_dict(self, mock_rt_cls):
        user = _make_user()
        type(user).is_superuser = PropertyMock(return_value=False)

        qs = self._mock_qs()
        mock_rt_cls.objects.filter.return_value = qs

        token_val = str(uuid.uuid4())
        mock_refresh = MagicMock()
        mock_refresh.token = token_val
        mock_rt_cls.objects.create.return_value = mock_refresh

        from apps.accounts.services.auth_service import issue_tokens_for_user
        result = issue_tokens_for_user(user)

        self.assertIn('access_token', result)
        self.assertIn('refresh_token', result)
        self.assertEqual(result['token_type'], 'Bearer')
        self.assertEqual(result['refresh_token'], token_val)

    @patch('apps.accounts.services.auth_service.RefreshToken')
    def test_revokes_existing_tokens(self, mock_rt_cls):
        user = _make_user()
        type(user).is_superuser = PropertyMock(return_value=False)

        qs = self._mock_qs()
        mock_rt_cls.objects.filter.return_value = qs

        mock_refresh = MagicMock()
        mock_refresh.token = str(uuid.uuid4())
        mock_rt_cls.objects.create.return_value = mock_refresh

        from apps.accounts.services.auth_service import issue_tokens_for_user
        issue_tokens_for_user(user)

        mock_rt_cls.objects.filter.assert_called_once_with(user=user, is_revoked=False)
        qs.update.assert_called_once()


class RotateRefreshTokenTest(TestCase):
    """Tests de auth_service.rotate_refresh_token."""

    @patch('apps.accounts.services.auth_service.RefreshToken')
    def test_valid_token_returns_new_pair(self, mock_rt_cls):
        user = _make_user()
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
        mock_rt_cls.objects.create.return_value = new_refresh

        from apps.accounts.services.auth_service import rotate_refresh_token
        result = rotate_refresh_token(str(uuid.uuid4()))

        self.assertIsNotNone(result)
        self.assertIn('access_token', result)
        self.assertEqual(result['refresh_token'], new_token_val)

    @patch('apps.accounts.services.auth_service.RefreshToken')
    def test_invalid_token_returns_none(self, mock_rt_cls):
        mock_rt_cls.objects.filter.return_value.first.return_value = None
        from apps.accounts.services.auth_service import rotate_refresh_token
        result = rotate_refresh_token(str(uuid.uuid4()))
        self.assertIsNone(result)

    @patch('apps.accounts.services.auth_service.RefreshToken')
    def test_expired_token_returns_none(self, mock_rt_cls):
        user = _make_user()
        old_refresh = MagicMock()
        old_refresh.is_revoked = False
        old_refresh.expires_at = timezone.now() - timedelta(seconds=1)
        old_refresh.user = user
        old_refresh.user.pk = user.pk

        mock_rt_cls.objects.filter.return_value.first.return_value = old_refresh

        from apps.accounts.services.auth_service import rotate_refresh_token
        result = rotate_refresh_token(str(uuid.uuid4()))

        self.assertIsNone(result)
        mock_rt_cls.objects.filter.return_value.update.assert_called_once()


class RevokeRefreshTokenTest(TestCase):
    """Tests de auth_service.revoke_refresh_token."""

    @patch('apps.accounts.services.auth_service.RefreshToken')
    def test_valid_token_revokes_and_returns_true(self, mock_rt_cls):
        user = _make_user()
        refresh = MagicMock()
        refresh.user = user
        refresh.user.pk = user.pk

        mock_rt_cls.objects.filter.return_value.first.return_value = refresh

        from apps.accounts.services.auth_service import revoke_refresh_token
        result = revoke_refresh_token(str(uuid.uuid4()))

        self.assertTrue(result)
        mock_rt_cls.objects.filter.return_value.update.assert_called_once()
        user.save.assert_called_once()

    @patch('apps.accounts.services.auth_service.RefreshToken')
    def test_invalid_token_returns_false(self, mock_rt_cls):
        mock_rt_cls.objects.filter.return_value.first.return_value = None

        from apps.accounts.services.auth_service import revoke_refresh_token
        result = revoke_refresh_token(str(uuid.uuid4()))

        self.assertFalse(result)


class GetUserInfoTest(TestCase):
    """Tests de auth_service.get_user_info."""

    @patch('apps.accounts.services.auth_service.get_roles_and_permissions', return_value=(['admin'], ['PERM_A']))
    @patch('apps.accounts.services.auth_service.User')
    def test_valid_token_returns_user_info(self, mock_user_cls, mock_rp):
        user = _make_user(id=42)
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_user_cls.objects.filter.return_value.first.return_value = user

        token = _make_access_token(user_id=42)

        from apps.accounts.services.auth_service import get_user_info
        result = get_user_info(token)

        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 42)
        self.assertEqual(result['username'], user.username)
        self.assertEqual(result['email'], user.email)
        self.assertIn('roles', result)
        self.assertIn('permissions', result)

    def test_invalid_token_returns_none(self):
        from apps.accounts.services.auth_service import get_user_info
        result = get_user_info('not.a.valid.jwt')
        self.assertIsNone(result)

    def test_expired_token_returns_none(self):
        token = _make_access_token(user_id=1, expired=True)
        from apps.accounts.services.auth_service import get_user_info
        result = get_user_info(token)
        self.assertIsNone(result)

    @patch('apps.accounts.services.auth_service.User')
    def test_deleted_user_returns_none(self, mock_user_cls):
        user = _make_user()
        type(user).is_deleted = PropertyMock(return_value=True)
        mock_user_cls.objects.filter.return_value.first.return_value = user

        token = _make_access_token(user_id=1)
        from apps.accounts.services.auth_service import get_user_info
        result = get_user_info(token)
        self.assertIsNone(result)

    @patch('apps.accounts.services.auth_service.User')
    def test_inactive_user_returns_none(self, mock_user_cls):
        user = _make_user(status='inactive')
        type(user).is_deleted = PropertyMock(return_value=False)
        mock_user_cls.objects.filter.return_value.first.return_value = user

        token = _make_access_token(user_id=1)
        from apps.accounts.services.auth_service import get_user_info
        result = get_user_info(token)
        self.assertIsNone(result)

    @patch('apps.accounts.services.auth_service.User')
    def test_user_not_found_returns_none(self, mock_user_cls):
        mock_user_cls.objects.filter.return_value.first.return_value = None

        token = _make_access_token(user_id=999)
        from apps.accounts.services.auth_service import get_user_info
        result = get_user_info(token)
        self.assertIsNone(result)


class IntrospectTokenTest(TestCase):
    """Tests de auth_service.introspect_token."""

    @patch('apps.accounts.services.auth_service.get_roles_and_permissions', return_value=([], []))
    @patch('apps.accounts.services.auth_service.User')
    def test_valid_token_returns_payload(self, mock_user_cls, mock_rp):
        user = _make_user(id=5)
        type(user).is_deleted = PropertyMock(return_value=False)
        type(user).is_superuser = PropertyMock(return_value=False)
        mock_user_cls.objects.filter.return_value.first.return_value = user

        token = _make_access_token(user_id=5)
        from apps.accounts.services.auth_service import introspect_token
        result = introspect_token(token)

        self.assertIsNotNone(result)
        self.assertEqual(result['user_id'], 5)

    def test_invalid_token_returns_none(self):
        from apps.accounts.services.auth_service import introspect_token
        result = introspect_token('garbage')
        self.assertIsNone(result)

    def test_expired_token_returns_none(self):
        token = _make_access_token(user_id=1, expired=True)
        from apps.accounts.services.auth_service import introspect_token
        result = introspect_token(token)
        self.assertIsNone(result)

    @patch('apps.accounts.services.auth_service.User')
    def test_user_not_found_returns_none(self, mock_user_cls):
        mock_user_cls.objects.filter.return_value.first.return_value = None
        token = _make_access_token(user_id=404)
        from apps.accounts.services.auth_service import introspect_token
        result = introspect_token(token)
        self.assertIsNone(result)



LOGIN_URL = '/auth/login'
REFRESH_URL = '/auth/refresh'
LOGOUT_URL = '/auth/logout'
VALIDATE_URL = '/auth/validate'
LOOKUP_URL = '/auth/users/lookup'

_FAKE_TOKENS = {
    'access_token': 'fake.access.token',
    'refresh_token': str(uuid.uuid4()),
    'token_type': 'Bearer',
}


class LoginViewTest(TestCase):
    """Tests de POST /auth/login."""

    def setUp(self):
        self.client = APIClient()

    @patch('apps.accounts.api.views.log_audit')
    @patch('apps.accounts.api.views.issue_tokens_for_user', return_value=_FAKE_TOKENS)
    @patch('apps.accounts.api.views.authenticate_user')
    def test_valid_credentials_return_200(self, mock_auth, mock_issue, mock_log):
        mock_auth.return_value = _make_user()
        resp = self.client.post(LOGIN_URL, {'username': 'testuser', 'password': 'pass'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access_token', resp.data)
        self.assertIn('refresh_token', resp.data)

    @patch('apps.accounts.api.views.log_audit')
    @patch('apps.accounts.api.views.authenticate_user', return_value=None)
    def test_invalid_credentials_return_401(self, mock_auth, mock_log):
        resp = self.client.post(LOGIN_URL, {'username': 'bad', 'password': 'wrong'}, format='json')
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.data['detail'], 'Invalid credentials.')

    def test_missing_fields_return_400(self):
        resp = self.client.post(LOGIN_URL, {'username': 'only'}, format='json')
        self.assertEqual(resp.status_code, 400)

    @patch('apps.accounts.api.views.log_audit')
    @patch('apps.accounts.api.views.authenticate_user', return_value=None)
    def test_inactive_user_return_401(self, mock_auth, mock_log):
        """authenticate_user ya devuelve None para usuarios inactivos."""
        resp = self.client.post(LOGIN_URL, {'username': 'inactive', 'password': 'pass'}, format='json')
        self.assertEqual(resp.status_code, 401)

    @patch('apps.accounts.api.views.log_audit')
    @patch('apps.accounts.api.views.authenticate_user', return_value=None)
    def test_deleted_user_returns_401(self, mock_auth, mock_log):
        resp = self.client.post(LOGIN_URL, {'username': 'deleted', 'password': 'pass'}, format='json')
        self.assertEqual(resp.status_code, 401)

    @patch('apps.accounts.api.views.log_audit')
    @patch('apps.accounts.api.views.authenticate_user', return_value=None)
    def test_locked_account_returns_401(self, mock_auth, mock_log):
        resp = self.client.post(LOGIN_URL, {'username': 'locked', 'password': 'pass'}, format='json')
        self.assertEqual(resp.status_code, 401)

    @patch('apps.accounts.api.views.log_audit')
    @patch('apps.accounts.api.views.issue_tokens_for_user', return_value=_FAKE_TOKENS)
    @patch('apps.accounts.api.views.authenticate_user')
    def test_successful_login_calls_log_audit(self, mock_auth, mock_issue, mock_log):
        user = _make_user()
        mock_auth.return_value = user
        self.client.post(LOGIN_URL, {'username': 'testuser', 'password': 'pass'}, format='json')
        mock_log.assert_called_once()

    @patch('apps.accounts.api.views.log_audit')
    @patch('apps.accounts.api.views.authenticate_user', return_value=None)
    def test_failed_login_calls_log_audit(self, mock_auth, mock_log):
        self.client.post(LOGIN_URL, {'username': 'x', 'password': 'y'}, format='json')
        mock_log.assert_called_once()


class RefreshViewTest(TestCase):
    """Tests de POST /auth/refresh."""

    def setUp(self):
        self.client = APIClient()
        self.valid_token = str(uuid.uuid4())

    @patch('apps.accounts.api.views.rotate_refresh_token', return_value=_FAKE_TOKENS)
    def test_valid_token_returns_200(self, mock_rotate):
        resp = self.client.post(REFRESH_URL, {'refresh_token': self.valid_token}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access_token', resp.data)

    @patch('apps.accounts.api.views.rotate_refresh_token', return_value=None)
    def test_invalid_token_returns_401(self, mock_rotate):
        resp = self.client.post(REFRESH_URL, {'refresh_token': self.valid_token}, format='json')
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.data['detail'], 'Invalid refresh token.')

    @patch('apps.accounts.api.views.rotate_refresh_token', return_value=None)
    def test_expired_token_returns_401(self, mock_rotate):
        """Para la vista, un token vencido es lo mismo que uno invalido."""
        resp = self.client.post(REFRESH_URL, {'refresh_token': self.valid_token}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_missing_refresh_token_returns_400(self):
        resp = self.client.post(REFRESH_URL, {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_malformed_uuid_returns_400(self):
        resp = self.client.post(REFRESH_URL, {'refresh_token': 'not-a-uuid'}, format='json')
        self.assertEqual(resp.status_code, 400)


class LogoutViewTest(TestCase):
    """Tests de POST /auth/logout."""

    def setUp(self):
        self.client = APIClient()
        self.valid_token = str(uuid.uuid4())

    @patch('apps.accounts.api.views.log_audit')
    @patch('apps.accounts.api.views.revoke_refresh_token', return_value=True)
    def test_valid_token_returns_200(self, mock_revoke, mock_log):
        resp = self.client.post(LOGOUT_URL, {'refresh_token': self.valid_token}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['detail'], 'Logged out.')

    @patch('apps.accounts.api.views.revoke_refresh_token', return_value=False)
    def test_invalid_token_returns_401(self, mock_revoke):
        resp = self.client.post(LOGOUT_URL, {'refresh_token': self.valid_token}, format='json')
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.data['detail'], 'Invalid refresh token.')

    def test_missing_token_returns_400(self):
        resp = self.client.post(LOGOUT_URL, {}, format='json')
        self.assertEqual(resp.status_code, 400)


class ValidateViewTest(TestCase):
    """Tests de GET /auth/validate."""

    def setUp(self):
        self.client = APIClient()
        self.valid_user_info = {
            'id': 1,
            'email': 'user@example.com',
            'username': 'testuser',
            'name': 'Test User',
            'roles': ['admin'],
            'permissions': ['USER_READ'],
        }

    @patch('apps.accounts.api.views.get_user_info')
    def test_valid_token_returns_200(self, mock_info):
        mock_info.return_value = self.valid_user_info
        resp = self.client.get(VALIDATE_URL, HTTP_AUTHORIZATION='Bearer validtoken')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['id'], 1)
        self.assertEqual(resp.data['username'], 'testuser')

    @patch('apps.accounts.api.views.get_user_info', return_value=None)
    def test_invalid_token_returns_401(self, mock_info):
        resp = self.client.get(VALIDATE_URL, HTTP_AUTHORIZATION='Bearer invalidtoken')
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.data['detail'], 'Invalid or expired token.')

    def test_missing_authorization_header_returns_401(self):
        resp = self.client.get(VALIDATE_URL)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.data['detail'], 'Authorization header missing or invalid.')

    def test_non_bearer_scheme_returns_401(self):
        resp = self.client.get(VALIDATE_URL, HTTP_AUTHORIZATION='Basic dXNlcjpwYXNz')
        self.assertEqual(resp.status_code, 401)


class UserLookupViewTest(TestCase):
    """Tests de GET /auth/users/lookup."""

    def setUp(self):
        self.client = APIClient()
        self.svc = {'HTTP_X_SERVICE_API_KEY': settings.SERVICE_API_KEY}
        self.boot = User.objects.create_superuser('boot', 'boot@example.com', 'pw')
        self.john = User.objects.create_user(
            'john', 'john@example.com', 'pw', created_by=self.boot, name='John Doe',
        )

    def test_missing_auth_returns_401(self):
        resp = self.client.get(LOOKUP_URL + '?q=john')
        self.assertEqual(resp.status_code, 401)

    def test_regular_user_forbidden(self):
        token = _make_access_token(user_id=self.john.id)
        resp = self.client.get(LOOKUP_URL + '?q=john', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(resp.status_code, 403)

    def test_service_key_can_lookup_by_username(self):
        resp = self.client.get(LOOKUP_URL + '?q=john', **self.svc)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['count'], 1)
        self.assertIn('john', [r['username'] for r in resp.data['results']])

    def test_service_key_can_lookup_by_email(self):
        resp = self.client.get(LOOKUP_URL + '?q=john@example', **self.svc)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['count'], 1)

    def test_missing_q_returns_400(self):
        resp = self.client.get(LOOKUP_URL, **self.svc)
        self.assertEqual(resp.status_code, 400)

    def test_no_match_returns_empty(self):
        resp = self.client.get(LOOKUP_URL + '?q=zzznobodyzzz', **self.svc)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)
        self.assertEqual(resp.data['results'], [])


class UsersByIdsViewTest(TestCase):
    """Tests de GET /auth/users/by-ids."""

    BY_IDS_URL = '/auth/users/by-ids'

    def setUp(self):
        self.client = APIClient()
        self.svc = {'HTTP_X_SERVICE_API_KEY': settings.SERVICE_API_KEY}
        self.boot = User.objects.create_superuser('boot', 'boot@example.com', 'pw')
        self.john = User.objects.create_user(
            'john', 'john@example.com', 'pw', created_by=self.boot, name='John',
        )

    def test_service_key_includes_email(self):
        resp = self.client.get(f'{self.BY_IDS_URL}?ids={self.john.id}', **self.svc)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['email'], 'john@example.com')

    def test_regular_user_hides_email(self):
        token = _make_access_token(user_id=self.john.id)
        resp = self.client.get(
            f'{self.BY_IDS_URL}?ids={self.john.id}', HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('email', resp.data['results'][0])
        self.assertEqual(resp.data['results'][0]['username'], 'john')

    def test_missing_ids_returns_400(self):
        resp = self.client.get(self.BY_IDS_URL, **self.svc)
        self.assertEqual(resp.status_code, 400)
