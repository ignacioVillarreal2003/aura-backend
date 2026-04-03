import logging

from app.application.services.document.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentUnauthorizedException
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.user.user_roles import ALL_ROLES

logger = logging.getLogger(__name__)

_PERMISSION_DOCUMENT_CREATE = "DOCUMENT_CREATE"
_REQUIRED_PERMISSIONS = {_PERMISSION_DOCUMENT_CREATE}


class CreateDocumentServiceAuthorizer:
    @staticmethod
    def require_permissions(
            authenticated_user: AuthenticatedUser
    ) -> None:
        if authenticated_user.has_all_permissions(_REQUIRED_PERMISSIONS):
            return

        user_permissions = set(authenticated_user.permissions)
        missing = _REQUIRED_PERMISSIONS - user_permissions
        logger.warning(
            "Insufficient permissions for document creation.",
            extra={
                "user_id": authenticated_user.id,
                "missing_permissions": sorted(missing),
                "user_permissions": sorted(user_permissions)
            }
        )
        raise CreateDocumentUnauthorizedException("You do not have permission to create documents.")

    @staticmethod
    def require_roles(
            authenticated_user: AuthenticatedUser,
            allowed_roles: set[str] = ALL_ROLES
    ) -> None:
        if authenticated_user.has_any_role(allowed_roles):
            return

        logger.warning(
            "Insufficient role for document creation.",
            extra={
                "user_id": authenticated_user.id,
                "user_roles": sorted(authenticated_user.roles),
                "allowed_roles": sorted(allowed_roles)
            }
        )
        raise CreateDocumentUnauthorizedException("You do not have the required role to create documents.")
