import logging
from fastapi import HTTPException, Request, status, Depends

from app.infrastructure.authentication_provider.dtos.authentication_response import (
    AuthenticationResponse
)
from app.infrastructure.authentication_provider.interfaces.authentication_provider_interface import \
    AuthenticationProviderInterface

logger = logging.getLogger(__name__)


async def get_authentication_provider(
        request: Request
) -> AuthenticationProviderInterface:
    try:
        authentication_provider: AuthenticationProviderInterface = request.app.state.authentication_provider
        return authentication_provider

    except AttributeError:
        logger.error("AuthenticationProvider not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service not configured",
        )


def get_current_user(
        request: Request
) -> AuthenticationResponse:
    user = getattr(request.state, "user", None)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    return user


def get_optional_user(
        request: Request
) -> AuthenticationResponse | None:
    return getattr(request.state, "user", None)


def require_roles(
        *required_roles: str
):
    def check_roles(
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> AuthenticationResponse:
        if not user.has_any_role(list(required_roles)):
            logger.warning(
                f"User {user.id} lacks required roles. "
                f"Has: {user.roles}, Required: {required_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {', '.join(required_roles)}"
            )
        return user

    return check_roles


def require_all_roles(
        *required_roles: str
):
    def check_roles(
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> AuthenticationResponse:
        if not user.has_all_roles(list(required_roles)):
            logger.warning(
                f"User {user.id} lacks all required roles. "
                f"Has: {user.roles}, Required all: {required_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required all roles: {', '.join(required_roles)}"
            )
        return user

    return check_roles


def require_permission(
        permission: str
):
    def check_permission(
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> AuthenticationResponse:
        return user

    return check_permission
