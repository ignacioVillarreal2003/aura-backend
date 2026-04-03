import logging

from app.application.services.document.document_query_service.exceptions.document_query_service_exception import (
    DocumentQueryUnauthorizedException
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.models.document import Document

logger = logging.getLogger(__name__)

_PERMISSION_DOCUMENT_GET = "DOCUMENT_GET"
_REQUIRED_PERMISSIONS = {_PERMISSION_DOCUMENT_GET}


class DocumentQueryServiceAuthorizer:
    @staticmethod
    def require_permissions(authenticated_user: AuthenticatedUser) -> None:
        if authenticated_user.has_all_permissions(_REQUIRED_PERMISSIONS):
            return
        user_permissions = set(authenticated_user.permissions)
        missing = _REQUIRED_PERMISSIONS - user_permissions

        logger.warning(
            "Insufficient permissions for the document query operation.",
            extra={
                "user_id": authenticated_user.id,
                "missing_permissions": sorted(missing),
                "user_permissions": sorted(user_permissions)
            }
        )
        raise DocumentQueryUnauthorizedException("You do not have permission to query documents.")

    @staticmethod
    def require_roles(
            authenticated_user: AuthenticatedUser,
            allowed_roles: set[str]
    ) -> None:
        if authenticated_user.has_any_role(allowed_roles):
            return

        logger.warning(
            "Insufficient role for the document query operation.",
            extra={
                "user_id": authenticated_user.id,
                "user_roles": sorted(authenticated_user.roles),
                "allowed_roles": sorted(allowed_roles)
            }
        )
        raise DocumentQueryUnauthorizedException("You do not have the required role for this document query.")

    @staticmethod
    def require_ownership(
            document: Document,
            authenticated_user: AuthenticatedUser
    ) -> None:
        if document.created_by == authenticated_user.id:
            return

        logger.warning(
            "An unauthorized document access was attempted.",
            extra={
                "document_id": document.id,
                "owner_id": document.created_by,
                "user_id": authenticated_user.id
            }
        )
        raise DocumentQueryUnauthorizedException("You are not authorized to access this document.")
