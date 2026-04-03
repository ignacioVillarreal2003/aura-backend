import logging

from app.application.services.fragment.post_process_fragment_service.exceptions.post_process_fragment_service_exception import (
    PostProcessFragmentUnauthorizedException
)
from app.domain.authentication.authenticated_user import AuthenticatedUser

logger = logging.getLogger(__name__)

_PERMISSION_FRAGMENT_UPDATE = "FRAGMENT_UPDATE"
_REQUIRED_PERMISSIONS = {_PERMISSION_FRAGMENT_UPDATE}


class PostProcessFragmentServiceAuthorizer:
    def require_permissions(
            self,
            authenticated_user: AuthenticatedUser
    ) -> None:
        if authenticated_user.has_all_permissions(_REQUIRED_PERMISSIONS):
            return
        user_permissions = set(authenticated_user.permissions)
        missing = _REQUIRED_PERMISSIONS - user_permissions

        logger.warning(
            "Insufficient permissions for the fragment post-processing operation.",
            extra={
                "user_id": authenticated_user.id,
                "missing_permissions": sorted(missing),
                "user_permissions": sorted(user_permissions)
            }
        )
        raise PostProcessFragmentUnauthorizedException("You do not have permission to run fragment post-processing.")

    @staticmethod
    def require_roles(
            authenticated_user: AuthenticatedUser,
            allowed_roles: set[str]
    ) -> None:
        if authenticated_user.has_any_role(allowed_roles):
            return

        logger.warning(
            "Insufficient role for the fragment post-processing operation.",
            extra={
                "user_id": authenticated_user.id,
                "user_roles": sorted(authenticated_user.roles),
                "allowed_roles": sorted(allowed_roles)
            }
        )
        raise PostProcessFragmentUnauthorizedException(
            "You do not have the required role for fragment post-processing."
        )
