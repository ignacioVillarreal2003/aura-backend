"""Authentication service functions for token issuance and introspection."""

import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.db.models import F
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.contrib.auth import authenticate

from accounts.models import RefreshToken, User
from accounts.request_token import get_request_token
from accounts.services.permission_cache import get_roles_and_permissions


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

    # Token revocation gate: reject any access token issued before the user's
    # ``tokens_valid_after`` cutoff. The cutoff is advanced by
    # ``revoke_all_sessions`` on logout / password change / admin force-logout,
    # which immediately invalidates every outstanding access token for the user
    # (bounded only by downstream validate caches). Tokens minted before this
    # feature shipped carry no ``iat`` and are allowed through until they expire
    # naturally — a backward-compatible rollout that avoids a mass re-login.
    # Comparison is at whole-second granularity (``iat`` is integer epoch
    # seconds) so a freshly minted token is never wrongly rejected.
    iat = payload.get('iat')
    valid_after = getattr(user, 'tokens_valid_after', None)
    if iat is not None and valid_after is not None and iat < int(valid_after.timestamp()):
        return None

    return user


def _build_access_token(user: User) -> str:
    now = timezone.now()
    expires_at = now + timedelta(minutes=settings.JWT_ACCESS_LIFETIME_MINUTES)
    payload = {
        'user_id': user.id,
        'is_super_admin': bool(user.is_superuser),
        'iat': int(now.timestamp()),
        'jti': uuid.uuid4().hex,
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
    return refresh


# ---------------------------------------------------------------------------
# Inter-service authorization
# ---------------------------------------------------------------------------

def mint_access_token(user: User) -> str:
    """Mint a short-lived access token for an internal service-to-service call.

    Used when an action originates from a context that has no end-user bearer
    token to forward (e.g. the Django admin, authenticated via session cookie).
    """
    return _build_access_token(user)


def get_outbound_authorization(user: User | None = None) -> str | None:
    """Return the ``Authorization`` header value for an outbound inter-service call.

    Prefers forwarding the caller's own bearer token so the downstream service
    acts with the real user's identity and permissions. When no token is being
    forwarded — typically Django admin flows authenticated via session cookie —
    a short-lived JWT is minted for the acting user instead.
    """
    forwarded = get_request_token()
    if forwarded:
        return forwarded
    if user is not None and getattr(user, 'is_authenticated', False):
        return f'Bearer {_build_access_token(user)}'
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def authenticate_user(username: str, password: str):
    user = authenticate(username=username, password=password)

    if not user:
        # Atomically increment failed attempts to avoid a lost-update race under
        # concurrent failed logins (which could otherwise let an attacker stay
        # below the lockout threshold via parallel tries).
        try:
            u = User.objects.get(username=username, deleted_at__isnull=True)
        except User.DoesNotExist:
            return None
        now = timezone.now()
        User.objects.filter(pk=u.pk).update(
            failed_login_attempts=Coalesce(F('failed_login_attempts'), 0) + 1,
            updated_at=now,
        )
        u.refresh_from_db(fields=['failed_login_attempts'])
        if u.failed_login_attempts >= settings.LOGIN_MAX_ATTEMPTS:
            User.objects.filter(pk=u.pk).update(
                lockout_until=now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES),
                account_non_locked=False,
                updated_at=now,
            )
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
    now = timezone.now()
    row = RefreshToken.objects.filter(token=token_value).first()
    if not row:
        return None
    # Reuse of an already-revoked refresh token signals possible theft (the
    # legitimate client already rotated it). Kill every session for safety.
    if row.is_revoked:
        revoke_all_sessions(row.user)
        return None
    # Atomically claim the token: this conditional UPDATE flips is_revoked
    # false->true and only ONE concurrent caller can win, preventing a
    # double-rotation race that would mint two valid token pairs.
    claimed = RefreshToken.objects.filter(pk=row.pk, is_revoked=False).update(
        is_revoked=True, updated_by=row.user_id, updated_at=now,
    )
    if not claimed:
        return None
    if row.expires_at <= now:
        return None
    new_refresh = _create_refresh_token(row.user, request=request)
    return {
        'access_token': _build_access_token(row.user),
        'refresh_token': new_refresh.token,
        'token_type': 'Bearer',
    }


def revoke_all_sessions(user: User) -> None:
    """Invalidate every active session for ``user``.

    Revokes all active refresh tokens AND advances ``tokens_valid_after`` so
    every outstanding access token (``iat`` < cutoff) is rejected by
    ``_decode_and_fetch_user`` on the next validate. Shared by logout, password
    change and the admin force-logout action.
    """
    now = timezone.now()
    RefreshToken.objects.filter(user=user, is_revoked=False).update(
        is_revoked=True,
        updated_by=user.pk,
        updated_at=now,
    )
    user.tokens_valid_after = now
    user.save(update_fields=['tokens_valid_after', 'updated_at'])


def revoke_refresh_token(refresh_token: uuid.UUID | str) -> bool:
    token_value = str(refresh_token)
    refresh = RefreshToken.objects.filter(token=token_value, is_revoked=False).first()
    if not refresh:
        return False
    # Logout ends the session: revoke refresh tokens AND kill outstanding access
    # tokens via the tokens_valid_after cutoff (consistent with the single-active
    # -session model that login already enforces).
    revoke_all_sessions(refresh.user)
    return True


def authenticate_access_token(token: str) -> User | None:
    """Return the active ``User`` for a valid access token, or ``None``.

    Used by the DRF ``JWTAuthentication`` class so views rely on the standard
    authentication/permission pipeline instead of parsing the Authorization
    header by hand. Applies the same revocation gate as every other validate
    path (see ``_decode_and_fetch_user``).
    """
    return _decode_and_fetch_user(token)


def introspect_token(token: str) -> dict | None:
    user = _decode_and_fetch_user(token)
    if not user:
        return None
    roles, permissions = get_roles_and_permissions(user)
    return {
        'user_id': user.id,
        'roles': roles,
        'permissions': permissions,
        'is_super_admin': user.is_superuser,
    }


def get_user_info(token: str) -> dict | None:
    user = _decode_and_fetch_user(token)
    if not user:
        return None
    roles, permissions = get_roles_and_permissions(user)
    return {
        'id': user.id,
        'email': user.email,
        'username': user.username,
        'name': user.name,
        'roles': roles,
        'permissions': permissions,
    }
