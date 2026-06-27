"""Funciones de autenticacion: emision e introspeccion de tokens."""

import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import authenticate

from accounts.models import RefreshToken, User
from accounts.request_token import get_request_token
from accounts.utils import get_user_permissions, get_user_roles



def _decode_and_fetch_user(token: str):
	"""Decodifica el JWT y devuelve el usuario activo, o None si algo falla."""
	try:
		payload = jwt.decode(
			token,
			settings.JWT_SIGNING_KEY,
			algorithms=[settings.JWT_ALGORITHM],
		)
	except jwt.PyJWTError:
		return None

	user_id = payload.get('user_id')
	if not user_id:
		return None

	user = User.objects.filter(id=user_id).first()
	if not user or user.is_deleted or user.status != 'active':
		return None

	if user.force_logout_at:
		from datetime import datetime, timezone as dt_tz
		token_issued_at = datetime.fromtimestamp(payload.get('iat', 0), tz=dt_tz.utc)
		if token_issued_at < user.force_logout_at:
			return None

	return user


def _build_access_token(user: User) -> str:
	now = timezone.now()
	expires_at = now + timedelta(minutes=settings.JWT_ACCESS_LIFETIME_MINUTES)
	payload = {
		'user_id': user.id,
		'is_super_admin': bool(user.is_superuser),
		'iat': int(now.timestamp()),
		'exp': int(expires_at.timestamp()),
	}
	return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm=settings.JWT_ALGORITHM)


def _create_refresh_token(user: User, request=None) -> RefreshToken:
	expires_at = timezone.now() + timedelta(days=settings.REFRESH_TOKEN_LIFETIME_DAYS)
	token_value = uuid.uuid4()

	ip_address = None
	user_agent = ''
	if request is not None:
		ip_address = request.META.get('REMOTE_ADDR')
		user_agent = request.META.get('HTTP_USER_AGENT', '')

	refresh = RefreshToken.objects.create(
		token=str(token_value),
		user=user,
		expires_at=expires_at,
		ip_address=ip_address,
		user_agent=user_agent,
		created_by=user.pk,
		updated_by=user.pk,
	)
	user.refresh_token = token_value
	user.save(update_fields=['refresh_token', 'updated_at'])
	return refresh



def mint_access_token(user: User) -> str:
	"""Genera un access token corto para una llamada entre servicios."""
	return _build_access_token(user)


def get_outbound_authorization(user: User | None = None) -> str | None:
	"""Devuelve el header Authorization para una llamada saliente."""
	forwarded = get_request_token()
	if forwarded:
		return forwarded
	if user is not None and getattr(user, 'is_authenticated', False):
		return f'Bearer {_build_access_token(user)}'
	return None



def authenticate_user(username: str, password: str):
	user = authenticate(username=username, password=password)

	if not user:
		try:
			u = User.objects.get(username=username, deleted_at__isnull=True)
			u.failed_login_attempts = (u.failed_login_attempts or 0) + 1
			if u.failed_login_attempts >= settings.LOGIN_MAX_ATTEMPTS:
				u.lockout_until = timezone.now() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
				u.account_non_locked = False
			u.save(update_fields=['failed_login_attempts', 'lockout_until', 'account_non_locked', 'updated_at'])
		except User.DoesNotExist:
			pass
		return None

	if user.is_deleted or user.status != 'active':
		return None
	if not user.account_non_locked:
		return None
	if user.lockout_until and user.lockout_until > timezone.now():
		return None

	user.failed_login_attempts = 0
	user.lockout_until = None
	user.account_non_locked = True
	user.last_login = timezone.now()
	user.force_logout_at = None
	user.save(update_fields=[
		'failed_login_attempts', 'lockout_until', 'account_non_locked',
		'last_login', 'force_logout_at', 'updated_at',
	])

	return user


def issue_tokens_for_user(user: User, request=None) -> dict:
	RefreshToken.objects.filter(user=user, is_revoked=False).update(
		is_revoked=True,
		updated_by=user.pk,
		updated_at=timezone.now(),
	)
	refresh = _create_refresh_token(user, request=request)
	access_token = _build_access_token(user)
	return {
		'access_token': access_token,
		'refresh_token': refresh.token,
		'token_type': 'Bearer',
	}


def issue_service_token_for_user(user: User) -> str:
	"""Genera un access token corto para llamadas del admin a otros servicios."""
	return _build_access_token(user)


def rotate_refresh_token(refresh_token: uuid.UUID | str, request=None) -> dict | None:
	token_value = str(refresh_token)
	refresh = RefreshToken.objects.filter(token=token_value, is_revoked=False).first()
	if not refresh:
		return None
	if refresh.expires_at <= timezone.now():
		refresh.is_revoked = True
		refresh.updated_by = refresh.user.pk
		refresh.save(update_fields=['is_revoked', 'updated_by', 'updated_at'])
		return None

	refresh.is_revoked = True
	refresh.updated_by = refresh.user.pk
	refresh.save(update_fields=['is_revoked', 'updated_by', 'updated_at'])

	_try_ldap_resync(refresh.user)

	new_refresh = _create_refresh_token(refresh.user, request=request)
	access_token = _build_access_token(refresh.user)
	return {
		'access_token': access_token,
		'refresh_token': new_refresh.token,
		'token_type': 'Bearer',
	}


def _try_ldap_resync(user: User) -> None:
	"""Vuelve a sincronizar MAC desde LDAP al rotar el token."""
	try:
		from accounts.ldap_backend import AuraLDAPBackend
		backend = AuraLDAPBackend()
		ldap_user_obj = backend.get_user(user.pk)
		if ldap_user_obj and hasattr(ldap_user_obj, '_ldap_user'):
			from accounts.ldap_sync import _sync_mac_attributes
			_sync_mac_attributes(sender=None, user=user, ldap_user=ldap_user_obj._ldap_user)
	except Exception as exc:
		import logging
		logging.getLogger(__name__).debug(
			"LDAP re-sync skipped for '%s': %s", user.username, exc
		)



def revoke_refresh_token(refresh_token: uuid.UUID | str) -> bool:
	token_value = str(refresh_token)
	refresh = RefreshToken.objects.filter(token=token_value, is_revoked=False).first()
	if not refresh:
		return False
	refresh.is_revoked = True
	refresh.updated_by = refresh.user.pk
	refresh.save(update_fields=['is_revoked', 'updated_by', 'updated_at'])
	refresh.user.refresh_token = None
	refresh.user.save(update_fields=['refresh_token', 'updated_at'])
	return True


def introspect_token(token: str) -> dict | None:
	user = _decode_and_fetch_user(token)
	if not user:
		return None
	return {
		'user_id': user.id,
		'roles': get_user_roles(user),
		'permissions': get_user_permissions(user),
		'is_super_admin': user.is_superuser,
	}


def get_user_info(token: str) -> dict | None:
	user = _decode_and_fetch_user(token)
	if not user:
		return None
	return {
		'id': user.id,
		'email': user.email,
		'username': user.username,
		'name': user.name,
		'roles': get_user_roles(user),
		'permissions': get_user_permissions(user),
	}
