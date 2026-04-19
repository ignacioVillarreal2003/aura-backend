"""Authentication service functions for token issuance and introspection."""

import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import authenticate

from accounts.models import RefreshToken, User
from accounts.utils import get_user_permissions, get_user_roles


def authenticate_user(username: str, password: str):
	user = authenticate(username=username, password=password)
	if not user:
		return None
	if user.is_deleted or user.status != 'active':
		return None
	if not user.account_non_locked:
		return None
	if user.lockout_until and user.lockout_until > timezone.now():
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


def _create_refresh_token(user: User) -> RefreshToken:
	expires_at = timezone.now() + timedelta(days=30)
	token_value = uuid.uuid4()
	refresh = RefreshToken.objects.create(
		token=str(token_value),
		user=user,
		expires_at=expires_at,
		created_by=user.pk,
		updated_by=user.pk,
	)
	user.refresh_token = token_value
	user.save(update_fields=['refresh_token', 'updated_at'])
	return refresh


def issue_tokens_for_user(user: User) -> dict:
	RefreshToken.objects.filter(user=user, is_revoked=False).update(
		is_revoked=True,
		updated_by=user.pk,
		updated_at=timezone.now(),
	)
	refresh = _create_refresh_token(user)
	access_token = _build_access_token(user)
	return {
		'access_token': access_token,
		'refresh_token': refresh.token,
		'token_type': 'Bearer',
	}


def rotate_refresh_token(refresh_token: uuid.UUID | str) -> dict | None:
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
	new_refresh = _create_refresh_token(refresh.user)
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


def get_user_info(token: str) -> dict | None:
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

	permissions = ['*'] if user.is_superuser else get_user_permissions(user)

	return {
		'id': user.id,
		'email': user.email,
		'username': user.username,
		'roles': get_user_roles(user),
		'permissions': permissions,
	}
