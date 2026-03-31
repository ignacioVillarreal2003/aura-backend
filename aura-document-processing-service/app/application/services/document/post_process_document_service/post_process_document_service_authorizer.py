import logging

from app.application.services.document.post_process_document_service.exceptions.post_process_document_service_exception import (
    PostProcessDocumentUnauthorizedException,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
logger = logging.getLogger(__name__)


class PostProcessDocumentServiceAuthorizer:
    _PERMISSION_DOCUMENT_UPDATE = "DOCUMENT_UPDATE"
    _REQUIRED_PERMISSIONS = {_PERMISSION_DOCUMENT_UPDATE}

    def require_permissions(self, authenticated_user: AuthenticatedUser) -> None:
        if authenticated_user.has_all_permissions(self._REQUIRED_PERMISSIONS):
            return
        user_permissions = set(authenticated_user.permissions)
        missing = self._REQUIRED_PERMISSIONS - user_permissions

        logger.warning(
            "Insufficient permissions for post-process document operation",
            extra={
                "user_id": authenticated_user.id,
                "missing_permissions": sorted(missing),
                "user_permissions": sorted(user_permissions),
            },
        )
        raise PostProcessDocumentUnauthorizedException(
            f"User {authenticated_user.id} is missing required permissions: {sorted(missing)}"
        )

    @staticmethod
    def require_roles(
            authenticated_user: AuthenticatedUser,
            allowed_roles: set[str],
    ) -> None:
        if authenticated_user.has_any_role(allowed_roles):
            return

        logger.warning(
            "Insufficient role for post-process document operation",
            extra={
                "user_id": authenticated_user.id,
                "user_roles": sorted(authenticated_user.roles),
                "allowed_roles": sorted(allowed_roles),
                "context": context,
            },
        )
        raise PostProcessDocumentUnauthorizedException(
            f"User {authenticated_user.id} is not authorized for {context}. "
            f"Allowed roles: {sorted(allowed_roles)}"
        )
