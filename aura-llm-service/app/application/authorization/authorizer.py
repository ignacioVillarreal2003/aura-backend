import logging

from app.application.authorization.exceptions.authorization_exceptions import UnauthorizedException
from app.domain.authentication.authenticated_user import AuthenticatedUser

logger = logging.getLogger(__name__)


class Authorizer:
    @staticmethod
    def require_permissions(
            authenticated_user: AuthenticatedUser,
            required_permissions: frozenset[str]
    ) -> None:
        if authenticated_user.has_all_permissions(required_permissions):
            return

        user_permissions = set(authenticated_user.permissions)
        missing = required_permissions - user_permissions
        logger.warning(
            "Insufficient permissions for the operation.",
            extra={
                "user_id": authenticated_user.id,
                "missing_permissions": sorted(missing),
                "user_permissions": sorted(user_permissions)
            }
        )
        raise UnauthorizedException("You do not have permission to perform this action.")
