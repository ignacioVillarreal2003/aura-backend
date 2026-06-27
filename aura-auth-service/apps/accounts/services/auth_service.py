"""Funciones de autenticacion: emision e introspeccion de tokens."""

import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.db.models import F
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.contrib.auth import authenticate

from apps.accounts.models import RefreshToken, User
from apps.accounts.request_token import get_request_token
from apps.accounts.services.permission_cache import get_roles_and_permissions



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



def mint_access_token(user: User) -> str:
    """Genera un access token corto para una llamada entre servicios."""
    return _build_access_token(user)


def get_outbound_authorization(user: User | None = None) -> str | None:
    """Devuelve el header Authorization para una llamada saliente.

    Reenvia el token del usuario si lo hay; si no (por ejemplo desde el admin),
    genera uno corto para el usuario que esta actuando.
    """
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
    """Genera un access token corto para llamadas del admin a otros servicios.

    El servicio destino lo valida igual que cualquier token de usuario, asi que
    se respetan los roles y permisos reales de ese usuario.
    """
    return _build_access_token(user)


def rotate_refresh_token(refresh_token: uuid.UUID | str, request=None) -> dict | None:
    token_value = str(refresh_token)
    now = timezone.now()
    row = RefreshToken.objects.filter(token=token_value).first()
    if not row:
        return None
    # Si reusan un refresh ya revocado, puede ser robo: cierro todas las sesiones
    if row.is_revoked:
        revoke_all_sessions(row.user)
        return None
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
    """Invalida todas las sesiones activas del usuario.

    Revoca los refresh tokens y adelanta tokens_valid_after para que tambien
    se rechacen los access tokens ya emitidos.
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
    revoke_all_sessions(refresh.user)
    return True


def authenticate_access_token(token: str) -> User | None:
    """Devuelve el usuario activo de un access token valido, o None."""
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
