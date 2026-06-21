"""Authentication service functions for token issuance and introspection."""

import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import authenticate

from accounts.models import RefreshToken, User
from accounts.utils import get_user_permissions, get_user_roles


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _decode_and_fetch_user(token: str):
	"""Decode a JWT and return the active User, or None on any failure."""
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

	return user


def _build_access_token(user: User) -> str:
	expires_at = timezone.now() + timedelta(minutes=settings.JWT_ACCESS_LIFETIME_MINUTES)
	payload = {
		'user_id': user.id,
		'is_super_admin': bool(user.is_superuser),
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def authenticate_user(username: str, password: str):
	user = authenticate(username=username, password=password)

	if not user:
		# Increment failed attempts for the matching user (if they exist)
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

	# Successful login — reset lockout counters and update last_login
	user.failed_login_attempts = 0
	user.lockout_until = None
	user.account_non_locked = True
	user.last_login = timezone.now()
	user.save(update_fields=[
		'failed_login_attempts', 'lockout_until', 'account_non_locked', 'last_login', 'updated_at',
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
	"""Mint a short-lived access token for `user`, with no refresh token and
	no RefreshToken row, for outbound admin-initiated service-to-service
	calls (e.g. Django admin -> chat-service) where the inbound request has
	no Bearer token to forward — admin pages are session-authenticated, not
	JWT-authenticated.

	The downstream service validates this exactly like any user-issued
	access token (GET /auth/validate), so the real RBAC roles/permissions of
	`user` are what gets enforced there — this is not a blanket
	service-trust bypass like the X-Service-Api-Key headers used for the MAC
	and document-processing clients.
	"""
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
	new_refresh = _create_refresh_token(refresh.user, request=request)
	access_token = _build_access_token(refresh.user)
	return {
		'access_token': access_token,
		'refresh_token': new_refresh.token,
		'token_type': 'Bearer',
	}


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
