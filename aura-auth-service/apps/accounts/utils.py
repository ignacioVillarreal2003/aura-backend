"""Funciones de apoyo para roles y permisos."""

from apps.accounts.models import User, Permission


def _normalize_permission_name(permission_name: str) -> str:
    """Pasa el nombre del permiso a MAYUSCULAS_CON_GUION_BAJO."""
    return (permission_name or '').strip().replace('.', '_').upper()


def user_has_permission(user: User, permission_name: str) -> bool:
    """Indica si el usuario tiene un permiso."""
    normalized_permission = _normalize_permission_name(permission_name)
    if user.is_superuser:
        return True
    return normalized_permission in get_user_permissions(user)


def get_user_permissions(user: User) -> list:
    """Devuelve todos los permisos de un usuario."""
    if user.is_superuser:
        permissions = [
            _normalize_permission_name(name)
            for name in Permission.objects.values_list('name', flat=True)
            if name
        ]
        return list(set(permissions))

    permissions = [
        _normalize_permission_name(name) for name in
        user.user_roles.filter(deleted_at__isnull=True).values_list(
            'role__permission_links__permission__name',
            flat=True,
        )
        if name
    ]
    return list(set(permissions))


def get_user_roles(user: User) -> list:
    """Devuelve todos los roles de un usuario."""
    roles = [
        name.lower() for name in
        user.user_roles.filter(deleted_at__isnull=True).values_list('role__name', flat=True)
        if name
    ]
    return list(set(roles))
