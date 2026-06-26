"""Permission helpers for the auth API."""

from rest_framework.permissions import BasePermission

from accounts.utils import user_has_permission

# End users need this RBAC permission to use the user directory; services are
# always allowed (they authenticate with the trusted X-Service-Api-Key).
_USER_DIRECTORY_PERM = 'ADMIN_USERS_VIEW'


def _is_service(user) -> bool:
    return getattr(user, 'is_service', False)


def can_view_user_directory(user) -> bool:
    """True for service principals or users holding the user-directory
    permission. Short-circuits on the service flag so it never touches the RBAC
    helpers for the non-DB-backed ServiceAccount principal."""
    if _is_service(user):
        return True
    return user_has_permission(user, _USER_DIRECTORY_PERM)


class IsServiceOrUserViewer(BasePermission):
    """Allow service-to-service callers, or end users with ``ADMIN_USERS_VIEW``.

    Used to gate the free-text user search (an enumeration / PII vector) so a
    plain authenticated end user cannot enumerate the directory.
    """

    message = 'No tenés permiso para consultar el directorio de usuarios.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated) and can_view_user_directory(user)
