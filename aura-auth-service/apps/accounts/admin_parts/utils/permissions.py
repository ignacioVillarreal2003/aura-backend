"""Helpers de control de acceso por permisos para el panel admin."""

from apps.accounts.admin_parts.utils.audit import _is_super_admin_user


def has_permission(request_or_user, permission_name: str) -> bool:
    """Indica si el usuario tiene un permiso, mirando sus roles en la base.

    Acepta un request o un usuario. Si es request y esta elevado, devuelve True.
    Cachea el resultado en el request para no repetir consultas.
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
