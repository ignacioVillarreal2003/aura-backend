"""Short-lived per-user cache of computed roles/permissions.

Used only by the token-validation hot path (``/auth/validate`` / introspect),
which every other service hits on (nearly) every request. Caching the computed
roles + permissions per user removes a burst of ``auth_db`` queries per
validate.

Design notes:
* Scope is deliberately the cross-service validate path only — the Django
  admin's own permission checks keep using the uncached helpers so they stay
  immediate. Downstream services already cache validate results too, so RBAC
  changes are eventually-consistent within the combined TTLs regardless.
* Graceful degradation: any Redis error falls back to a direct DB compute, so
  a cache outage slows validation down but never breaks it.
* Consistency: entries expire after ``PERMISSIONS_CACHE_TTL`` seconds;
  ``invalidate`` is also called on direct role assignment for immediacy.
"""
import logging

from django.core.cache import caches

from apps.accounts.utils import get_user_permissions, get_user_roles

logger = logging.getLogger(__name__)

_KEY = 'rp:{user_id}'


def _cache():
    return caches['permissions']


def get_roles_and_permissions(user) -> tuple[list, list]:
    """Return ``(roles, permissions)`` for ``user``, from cache when possible."""
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
    """Drop a user's cached roles/permissions (e.g. after a role change)."""
    try:
        _cache().delete(_KEY.format(user_id=user_id))
    except Exception:
        logger.warning('permissions cache invalidate failed for user %s', user_id, exc_info=True)
