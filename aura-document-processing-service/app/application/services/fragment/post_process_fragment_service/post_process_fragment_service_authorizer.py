import logging

from app.application.services.fragment.post_process_fragment_service.exceptions.post_process_fragment_service_exception import (
    PostProcessFragmentUnauthorizedException,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.authentication.user_roles import ADMIN_ROLES

logger = logging.getLogger(__name__)


class PostProcessFragmentServiceAuthorizer:
    _PERMISSION_FRAGMENT_UPDATE = "FRAGMENT_UPDATE"
    _REQUIRED_PERMISSIONS = {_PERMISSION_FRAGMENT_UPDATE}

    def require_permissions(self, authenticated_user: AuthenticatedUser) -> None:
        user_permissions = set(authenticated_user.permissions)
        missing = self._REQUIRED_PERMISSIONS - user_permissions
        if not missing:
            return

        logger.warning(
            "Insufficient permissions for post-process fragment operation",
            extra={
                "user_id": authenticated_user.id,
                "missing_permissions": sorted(missing),
                "user_permissions": sorted(user_permissions),
            },
        )
        raise PostProcessFragmentUnauthorizedException(
            f"User {authenticated_user.id} is missing required permissions: {sorted(missing)}"
        )

    @staticmethod
    def require_admin_role(authenticated_user: AuthenticatedUser, context: str) -> None:
        if bool(set(authenticated_user.roles) & ADMIN_ROLES):
            return

        logger.warning(
            "Insufficient role for post-process fragment operation",
            extra={
                "user_id": authenticated_user.id,
                "user_roles": sorted(authenticated_user.roles),
                "allowed_roles": sorted(ADMIN_ROLES),
                "context": context,
            },
        )
        raise PostProcessFragmentUnauthorizedException(
            f"User {authenticated_user.id} is not authorized for {context}. "
            f"Allowed roles: {sorted(ADMIN_ROLES)}"
        )
