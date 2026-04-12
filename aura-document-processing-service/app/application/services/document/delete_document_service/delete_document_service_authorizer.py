import logging

from app.application.services.document.delete_document_service.exceptions.delete_document_service_exception import (
    DeleteDocumentUnauthorizedException,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser

logger = logging.getLogger(__name__)

_PERMISSION_DOCUMENT_DELETE = "DOCUMENT_DELETE"
_PERMISSION_FRAGMENT_DELETE = "FRAGMENT_DELETE"
_REQUIRED_PERMISSIONS = {_PERMISSION_DOCUMENT_DELETE, _PERMISSION_FRAGMENT_DELETE}


class DeleteDocumentServiceAuthorizer:
    @staticmethod
    def require_permissions(
            authenticated_user: AuthenticatedUser
    ) -> None:
        if authenticated_user.has_all_permissions(_REQUIRED_PERMISSIONS):
            return

        user_permissions = set(authenticated_user.permissions)
        missing = _REQUIRED_PERMISSIONS - user_permissions
        logger.warning(
            "Insufficient permissions for the delete operation.",
            extra={
                "user_id": authenticated_user.id,
                "missing_permissions": sorted(missing),
                "user_permissions": sorted(user_permissions)
            },
        )
        raise DeleteDocumentUnauthorizedException("You do not have permission to delete documents or fragments.")

    @staticmethod
    def require_roles(
            authenticated_user: AuthenticatedUser,
            allowed_roles: set[str],
    ) -> None:
        if authenticated_user.has_any_role(allowed_roles):
            return

        logger.warning(
            "Insufficient role for the delete operation.",
            extra={
                "user_id": authenticated_user.id,
                "user_roles": sorted(authenticated_user.roles),
                "allowed_roles": sorted(allowed_roles)
            }
        )
        raise DeleteDocumentUnauthorizedException("You do not have the required role for this delete operation.")
