import logging

from core.authentication.authenticated_user import AuthenticatedUser
from core.exceptions.base import InsufficientPermissionsException

logger = logging.getLogger(__name__)


class AccessControl:
    @staticmethod
    def require_permissions(
        authenticated_user: AuthenticatedUser,
        required_permissions: frozenset[str],
    ) -> None:
        if getattr(authenticated_user, "is_service", False):
            return
        if authenticated_user.has_all_permissions(required_permissions):
            return
        user_permissions = set(authenticated_user.permissions)
        missing = required_permissions - user_permissions
        logger.warning(
            "Insufficient permissions for the operation.",
            extra={
                "user_id": authenticated_user.id,
                "missing_permissions": sorted(missing),
                "user_permissions": sorted(user_permissions),
            },
        )
        raise InsufficientPermissionsException(
            detail="You do not have permission to perform this action.",
            error_code="insufficient_permissions",
        )

    @staticmethod
    def require_super_admin(authenticated_user: AuthenticatedUser) -> None:
        if getattr(authenticated_user, "is_super_admin", False):
            return
        if authenticated_user.has_any_role(frozenset({"superadmin", "SUPERADMIN"})):
            return
        logger.warning(
            "Super-admin only operation attempted by a regular user.",
            extra={"user_id": authenticated_user.id},
        )
        raise InsufficientPermissionsException(
            detail="Super-admin role required.",
            error_code="superadmin_required",
        )
