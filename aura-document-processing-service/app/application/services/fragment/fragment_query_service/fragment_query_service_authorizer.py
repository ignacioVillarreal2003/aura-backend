import logging

from app.application.helpers.authentication_helper import has_any_role
from app.application.services.fragment.fragment_query_service.exceptions.fragment_query_service_exception import (
    FragmentQueryUnauthorizedException,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.authentication.user_roles import ALL_ROLES
from app.domain.models.document import Document

logger = logging.getLogger(__name__)


class FragmentQueryServiceAuthorizer:
    _PERMISSION_DOCUMENT_GET = "DOCUMENT_GET"
    _REQUIRED_PERMISSIONS = {_PERMISSION_DOCUMENT_GET}

    def require_permissions(self, authenticated_user: AuthenticatedUser) -> None:
        user_permissions = set(authenticated_user.permissions)
        missing = self._REQUIRED_PERMISSIONS - user_permissions
        if not missing:
            return

        logger.warning(
            "Insufficient permissions for fragment query operation",
            extra={
                "user_id": authenticated_user.id,
                "missing_permissions": sorted(missing),
                "user_permissions": sorted(user_permissions),
            },
        )
        raise FragmentQueryUnauthorizedException(
            f"User {authenticated_user.id} is missing required permissions: {sorted(missing)}"
        )

    def require_roles(
            self,
            authenticated_user: AuthenticatedUser,
            context: str
    ) -> None:
        if has_any_role(authenticated_user, ALL_ROLES):
            return

        logger.warning(
            "Insufficient role for fragment query operation",
            extra={
                "user_id": authenticated_user.id,
                "user_roles": sorted(authenticated_user.roles),
                "allowed_roles": sorted(ALL_ROLES),
                "context": context,
            },
        )
        raise FragmentQueryUnauthorizedException(
            f"User {authenticated_user.id} does not have the required role for {context}. "
            f"Allowed roles: {sorted(ALL_ROLES)}"
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
        raise FragmentQueryUnauthorizedException(
            f"User {authenticated_user.id} is not authorized to access document {document.id}"
        )
