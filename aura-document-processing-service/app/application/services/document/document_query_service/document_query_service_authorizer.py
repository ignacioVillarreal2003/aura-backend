import logging

from app.application.services.document.document_query_service.exceptions.document_query_service_exception import (
    DocumentQueryUnauthorizedException,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.models.document import Document

logger = logging.getLogger(__name__)


class DocumentQueryServiceAuthorizer:
    _PERMISSION_DOCUMENT_GET = "DOCUMENT_GET"
    _REQUIRED_PERMISSIONS = {_PERMISSION_DOCUMENT_GET}

    def require_permissions(self, authenticated_user: AuthenticatedUser) -> None:
        if authenticated_user.has_all_permissions(self._REQUIRED_PERMISSIONS):
            return
        user_permissions = set(authenticated_user.permissions)
        missing = self._REQUIRED_PERMISSIONS - user_permissions

        logger.warning(
            "Insufficient permissions for document query operation",
            extra={
                "user_id": authenticated_user.id,
                "missing_permissions": sorted(missing),
                "user_permissions": sorted(user_permissions),
            },
        )
        raise DocumentQueryUnauthorizedException(
            f"User {authenticated_user.id} is missing required permissions: {sorted(missing)}"
        )

    @staticmethod
    def require_roles(
            authenticated_user: AuthenticatedUser,
            allowed_roles: set[str]
    ) -> None:
        if authenticated_user.has_any_role(allowed_roles):
            return

        logger.warning(
            "Insufficient role for document query operation",
            extra={
                "user_id": authenticated_user.id,
                "user_roles": sorted(authenticated_user.roles),
                "allowed_roles": sorted(allowed_roles),
            },
        )
        raise DocumentQueryUnauthorizedException(
            f"User {authenticated_user.id} does not have the required role. "
            f"Allowed roles: {sorted(allowed_roles)}"
        )

    @staticmethod
    def require_ownership(document: Document, authenticated_user: AuthenticatedUser) -> None:
        if document.created_by == authenticated_user.id:
            return

        logger.warning(
            "Unauthorized document access attempt",
            extra={
                "document_id": document.id,
                "owner_id": document.created_by,
                "user_id": authenticated_user.id,
            },
        )
        raise DocumentQueryUnauthorizedException(
            f"User {authenticated_user.id} is not authorized to access document {document.id}"
        )
