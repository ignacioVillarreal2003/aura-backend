"""Cache corta por usuario de roles y permisos para el endpoint /auth/validate.

Si Redis falla se calcula directo de la base, asi que una caida de la cache
solo hace mas lento el validate pero no lo rompe.
"""
import logging

from django.core.cache import caches

from apps.accounts.utils import get_user_permissions, get_user_roles

logger = logging.getLogger(__name__)

_KEY = 'rp:{user_id}'


def _cache():
    return caches['permissions']


def get_roles_and_permissions(user) -> tuple[list, list]:
    """Devuelve (roles, permisos) del usuario, usando la cache si se puede."""
    key = _KEY.format(user_id=user.id)
    try:
        cached = _cache().get(key)
        if cached is not None:
            return cached['roles'], cached['permissions']
    except Exception:
        logger.warning('permissions cache read failed; computing from DB', exc_info=True)
        return get_user_roles(user), get_user_permissions(user)

    roles = get_user_roles(user)
    permissions = get_user_permissions(user)
    try:
        _cache().set(key, {'roles': roles, 'permissions': permissions})
    except Exception:
        logger.warning('permissions cache write failed', exc_info=True)
    return roles, permissions


def invalidate(user_id) -> None:
    """Borra los roles/permisos cacheados de un usuario."""
    try:
        _cache().delete(_KEY.format(user_id=user_id))
    except Exception:
        logger.warning('permissions cache invalidate failed for user %s', user_id, exc_info=True)
