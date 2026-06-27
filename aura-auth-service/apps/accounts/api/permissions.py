"""Helpers de permisos para la API de autenticacion."""

from rest_framework.permissions import BasePermission

from apps.accounts.utils import user_has_permission

_USER_DIRECTORY_PERM = 'ADMIN_USERS_VIEW'


def _is_service(user) -> bool:
    return getattr(user, 'is_service', False)


def can_view_user_directory(user) -> bool:
    """True para servicios o usuarios con el permiso del directorio."""
    if _is_service(user):
        return True
    return user_has_permission(user, _USER_DIRECTORY_PERM)


class IsServiceOrUserViewer(BasePermission):
    """Permite servicios o usuarios con ADMIN_USERS_VIEW."""

    message = 'No tenés permiso para consultar el directorio de usuarios.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated) and can_view_user_directory(user)
