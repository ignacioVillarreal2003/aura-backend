import logging

from app.application.services.document.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentUnauthorizedException,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.user.user_roles import ALL_ROLES

logger = logging.getLogger(__name__)


class CreateDocumentServiceAuthorizer:
    _PERMISSION_DOCUMENT_CREATE = "DOCUMENT_CREATE"
    _REQUIRED_PERMISSIONS = {_PERMISSION_DOCUMENT_CREATE}

    def require_permissions(self, authenticated_user: AuthenticatedUser) -> None:
        if authenticated_user.has_all_permissions(self._REQUIRED_PERMISSIONS):
            return

        user_permissions = set(authenticated_user.permissions)
        missing = self._REQUIRED_PERMISSIONS - user_permissions
        logger.warning(
            "Insufficient permissions for document creation",
            extra={
                "user_id": authenticated_user.id,
                "missing_permissions": sorted(missing),
                "user_permissions": sorted(user_permissions),
            },
        )
        raise CreateDocumentUnauthorizedException(
            f"User {authenticated_user.id} is missing required permissions: {sorted(missing)}"
        )

    @staticmethod
    def require_roles(
            authenticated_user: AuthenticatedUser,
            allowed_roles: set[str] = ALL_ROLES,
    ) -> None:
        if authenticated_user.has_any_role(allowed_roles):
            return

        logger.warning(
            "Insufficient role for document creation",
            extra={
                "user_id": authenticated_user.id,
                "user_roles": sorted(authenticated_user.roles),
                "allowed_roles": sorted(allowed_roles),
            },
        )
        raise CreateDocumentUnauthorizedException(
            f"User {authenticated_user.id} does not have the required role. "
            f"Allowed roles: {sorted(allowed_roles)}"
        )
