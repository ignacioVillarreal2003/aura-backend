import logging

from app.application.services.document.post_process_document_service.exceptions.post_process_document_service_exception import (
    PostProcessDocumentUnauthorizedException
)
from app.domain.authentication.authenticated_user import AuthenticatedUser

logger = logging.getLogger(__name__)

_PERMISSION_DOCUMENT_UPDATE = "DOCUMENT_UPDATE"
_REQUIRED_PERMISSIONS = {_PERMISSION_DOCUMENT_UPDATE}


class PostProcessDocumentServiceAuthorizer:
    @staticmethod
    def require_permissions(
            authenticated_user: AuthenticatedUser
    ) -> None:
        if authenticated_user.has_all_permissions(_REQUIRED_PERMISSIONS):
            return
        user_permissions = set(authenticated_user.permissions)
        missing = _REQUIRED_PERMISSIONS - user_permissions

        logger.warning(
            "Insufficient permissions for the document post-processing operation.",
            extra={
                "user_id": authenticated_user.id,
                "missing_permissions": sorted(missing),
                "user_permissions": sorted(user_permissions)
            }
        )
        raise PostProcessDocumentUnauthorizedException("You do not have permission to run document post-processing.")

    @staticmethod
    def require_roles(
            authenticated_user: AuthenticatedUser,
            allowed_roles: set[str]
    ) -> None:
        if authenticated_user.has_any_role(allowed_roles):
            return

        logger.warning(
            "Insufficient role for the document post-processing operation.",
            extra={
                "user_id": authenticated_user.id,
                "user_roles": sorted(authenticated_user.roles),
                "allowed_roles": sorted(allowed_roles)
            }
        )
        raise PostProcessDocumentUnauthorizedException(
            "You do not have the required role for document post-processing."
        )
