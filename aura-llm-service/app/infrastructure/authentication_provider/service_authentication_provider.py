import logging
import secrets
from typing import Optional

from fastapi import Header, HTTPException, status

from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.authentication_provider.service_authentication_settings import ServiceAuthSettings

logger = logging.getLogger(__name__)

_service_auth_settings: Optional[ServiceAuthSettings] = None


def _get_service_auth_settings() -> ServiceAuthSettings:
    global _service_auth_settings
    if _service_auth_settings is None:
        _service_auth_settings = ServiceAuthSettings()
    return _service_auth_settings


async def get_service_caller_user(
        x_service_api_key: Optional[str] = Header(default=None, alias="X-Service-Api-Key"),
        x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
        x_user_roles: Optional[str] = Header(default=None, alias="X-User-Roles"),
        x_user_permissions: Optional[str] = Header(default=None, alias="X-User-Permissions"),
) -> AuthenticationResponse:
    if not x_service_api_key:
        logger.warning("Service-to-service call missing X-Service-Api-Key header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service API key required",
        )

    settings = _get_service_auth_settings()

    if not secrets.compare_digest(x_service_api_key, settings.internal_service_api_key):
        logger.warning("Service-to-service call rejected: invalid X-Service-Api-Key")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid service API key",
        )

    if not x_user_id:
        logger.warning("Service-to-service call missing X-User-Id header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id header is required",
        )

    try:
        user_id = int(x_user_id)
    except ValueError:
        logger.warning(
            "Service-to-service call has non-integer X-User-Id",
            extra={"x_user_id": x_user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id must be a valid integer",
        )

    roles = [r.strip() for r in x_user_roles.split(",") if r.strip()] if x_user_roles else []
    permissions = (
        [p.strip() for p in x_user_permissions.split(",") if p.strip()]
        if x_user_permissions
        else []
    )

    logger.debug(
        "Service-to-service caller authenticated",
        extra={"user_id": user_id, "roles": roles},
    )

    return AuthenticationResponse(
        id=user_id,
        email="service-call",
        roles=roles,
        permissions=permissions,
    )
