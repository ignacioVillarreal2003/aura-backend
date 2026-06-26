"""Permission-driven access control helpers for the admin panel.

Admin panel permissions (ADMIN_*) are stored in the same permission/role tables
as service permissions. has_permission() checks the DB at request time and caches
the result on the request object to avoid repeated queries.
"""

from apps.accounts.admin_parts.utils.audit import _is_super_admin_user


def has_permission(request_or_user, permission_name: str) -> bool:
    """
    Check if user has a specific permission via DB lookup through role→permission links.

    Accepts either a request object or a user object:
    - If request: elevated admins (request.is_elevated = True) return True immediately,
      matching _is_effective_superadmin semantics — elevation grants full access.
    - If user only: no elevation check is performed.

    Uses request._permission_cache to avoid repeated DB queries within a single request.
    Django superusers always return True regardless of explicit permission assignments.
    """
    if hasattr(request_or_user, 'user'):
        request = request_or_user
        user = request.user
        if getattr(request, 'is_elevated', False):
            return True
    else:
        user = request_or_user
        request = None

    if not user or not getattr(user, 'is_authenticated', False):
        return False

    if _is_super_admin_user(user):
        return True

    if request is not None:
        cache = getattr(request, '_permission_cache', None)
        if cache is None:
            request._permission_cache = {}
            cache = request._permission_cache
        if permission_name in cache:
            return cache[permission_name]

    result = user.user_roles.filter(
        deleted_at__isnull=True,
        role__permission_links__permission__name=permission_name,
    ).exists()

    if request is not None:
        request._permission_cache[permission_name] = result

    return result
