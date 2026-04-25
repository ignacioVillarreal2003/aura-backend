import logging

from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.persistence.database.orm.document import Document

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

    @staticmethod
    def require_document_ownership(
            document: Document,
            authenticated_user: AuthenticatedUser
    ) -> None:
        if document.created_by == authenticated_user.id:
            return

        logger.warning(
            "Unauthorized document access attempt for document action.",
            extra={
                "document_id": document.id,
                "owner_id": document.created_by,
                "user_id": authenticated_user.id
            }
        )
        raise UnauthorizedException("You are not authorized to access this document.")
