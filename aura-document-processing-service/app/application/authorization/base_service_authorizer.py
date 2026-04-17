import logging
from typing import TYPE_CHECKING

from app.application.exceptions.app_exception import AppException
from app.domain.authentication.authenticated_user import AuthenticatedUser

if TYPE_CHECKING:
    from app.domain.models.document import Document

logger = logging.getLogger(__name__)


class BaseServiceAuthorizer:
    """
    Central authorization logic shared across all application services.

    Each concrete authorizer subclass configures:
      - The required permissions for its operation.
      - The specific UnauthorizedException to raise.
      - A human-readable label used in log messages.

    Services call require_permissions / require_roles / require_ownership
    exactly as before — no call-site changes needed.
    """

    def __init__(
        self,
        unauthorized_exception_class: type[AppException],
        required_permissions: frozenset[str],
        operation_label: str,
    ) -> None:
        self._unauthorized_exception_class = unauthorized_exception_class
        self._required_permissions = required_permissions
        self._operation_label = operation_label

    # ------------------------------------------------------------------
    # Public interface (mirrors the original per-service authorizers)
    # ------------------------------------------------------------------

    def require_permissions(self, authenticated_user: AuthenticatedUser) -> None:
        if authenticated_user.has_all_permissions(self._required_permissions):
            return

        user_permissions = set(authenticated_user.permissions)
        missing = self._required_permissions - user_permissions
        logger.warning(
            "Insufficient permissions for %s.",
            self._operation_label,
            extra={
                "user_id": authenticated_user.id,
                "missing_permissions": sorted(missing),
                "user_permissions": sorted(user_permissions),
            },
        )
        raise self._unauthorized_exception_class(
            f"You do not have permission to perform: {self._operation_label}."
        )

    def require_roles(
        self,
        authenticated_user: AuthenticatedUser,
        allowed_roles: set[str],
    ) -> None:
        if authenticated_user.has_any_role(allowed_roles):
            return

        logger.warning(
            "Insufficient role for %s.",
            self._operation_label,
            extra={
                "user_id": authenticated_user.id,
                "user_roles": sorted(authenticated_user.roles),
                "allowed_roles": sorted(allowed_roles),
            },
        )
        raise self._unauthorized_exception_class(
            f"You do not have the required role for: {self._operation_label}."
        )

    def require_ownership(
        self,
        document: "Document",
        authenticated_user: AuthenticatedUser,
    ) -> None:
        if document.created_by == authenticated_user.id:
            return

        logger.warning(
            "Unauthorized document access attempt during %s.",
            self._operation_label,
            extra={
                "document_id": document.id,
                "owner_id": document.created_by,
                "user_id": authenticated_user.id,
            },
        )
        raise self._unauthorized_exception_class(
            "You are not authorized to access this document."
        )
