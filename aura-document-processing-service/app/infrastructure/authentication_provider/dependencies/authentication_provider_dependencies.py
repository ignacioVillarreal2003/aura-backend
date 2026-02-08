from fastapi import HTTPException, Request, status, Depends

from app.configuration.environment_variables import environment_variables
from app.infrastructure.authentication_provider.authentication_provider import AuthenticationProvider
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.authentication_provider.interfaces.authentication_provider_interface import (
    AuthenticationProviderInterface
)
from app.infrastructure.http_client.http_client_factory import get_http_client


def get_authentication_provider() -> AuthenticationProviderInterface:
    http_client = get_http_client()
    return AuthenticationProvider.create(
        http_client=http_client,
        authentication_validate_token_url=environment_variables.authentication_validate_token_url,
        authentication_verify_permissions_url=environment_variables.authentication_verify_permissions_url,
        authentication_get_user_by_token_url=environment_variables.authentication_get_user_by_token_url
    )


def get_current_user(
        request: Request
) -> AuthenticationResponse:
    user = getattr(request.state, "user", None)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    return user


def get_optional_user(
        request: Request
) -> AuthenticationResponse | None:
    return getattr(request.state, "user", None)


def require_roles(*required_roles: str):
    def check_roles(
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> AuthenticationResponse:
        if not user.has_any_role(list(required_roles)):
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
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required all roles: {', '.join(required_roles)}"
            )
        return user

    return check_roles
