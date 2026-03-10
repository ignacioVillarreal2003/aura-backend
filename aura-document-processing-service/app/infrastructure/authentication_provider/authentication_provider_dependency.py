import logging
from typing import Optional
from fastapi import HTTPException, Request, status

from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.authentication_provider.interfaces.authentication_provider_interface import (
    AuthenticationProviderInterface
)

logger = logging.getLogger(__name__)


async def get_authentication_provider(request: Request) -> AuthenticationProviderInterface:
    try:
        return request.app.state.authentication_provider
    except AttributeError:
        logger.error("AuthenticationProvider not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AuthenticationProvider not configured"
        )


def get_current_user(request: Request) -> AuthenticationResponse:
    user: Optional[AuthenticationResponse] = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )
    return user
