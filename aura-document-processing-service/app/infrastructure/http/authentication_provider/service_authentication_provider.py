import logging
import secrets
from dataclasses import dataclass
from typing import Optional, Union

from starlette.requests import Request

from app.domain.models.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.service_authentication_settings import ServiceAuthSettings

logger = logging.getLogger(__name__)

_service_auth_settings: Optional[ServiceAuthSettings] = None

HEADER_SERVICE_API_KEY = "X-Service-Api-Key"
HEADER_USER_ID = "X-User-Id"
HEADER_USER_EMAIL = "X-User-Email"
HEADER_USER_ROLES = "X-User-Roles"
HEADER_USER_PERMISSIONS = "X-User-Permissions"


def _get_service_auth_settings() -> ServiceAuthSettings:
    global _service_auth_settings
    if _service_auth_settings is None:
        _service_auth_settings = ServiceAuthSettings()
    return _service_auth_settings


@dataclass(frozen=True)
class ServiceAuthSkip:
    """No X-Service-Api-Key; continue with Bearer/JWT flow."""


@dataclass(frozen=True)
class ServiceAuthSuccess:
    user: AuthenticatedUser


@dataclass(frozen=True)
class ServiceAuthError:
    status_code: int
    detail: str
    error: str


ServiceAuthOutcome = Union[ServiceAuthSkip, ServiceAuthSuccess, ServiceAuthError]


def evaluate_service_authentication(
        request: Request,
        settings: Optional[ServiceAuthSettings] = None,
) -> ServiceAuthOutcome:
    """
    If the request includes X-Service-Api-Key, validate it and build AuthenticatedUser from headers.
    If the header is absent, return ServiceAuthSkip.
    """
    raw_key = request.headers.get(HEADER_SERVICE_API_KEY)
    if raw_key is None:
        return ServiceAuthSkip()

    api_key = raw_key.strip()
    if not api_key:
        logger.warning(
            "Service-to-service call: empty X-Service-Api-Key",
            extra={"path": request.url.path},
        )
        return ServiceAuthError(
            status_code=401,
            detail="Service API key required",
            error="missing_service_key",
        )

    cfg = settings or _get_service_auth_settings()
    if not secrets.compare_digest(api_key, cfg.internal_service_api_key):
        logger.warning(
            "Service-to-service call rejected: invalid X-Service-Api-Key",
            extra={"path": request.url.path},
        )
        return ServiceAuthError(
            status_code=403,
            detail="Invalid service API key",
            error="invalid_service_key",
        )

    x_user_id = request.headers.get(HEADER_USER_ID)
    if not x_user_id or not x_user_id.strip():
        logger.warning(
            "Service-to-service call missing X-User-Id",
            extra={"path": request.url.path},
        )
        return ServiceAuthError(
            status_code=400,
            detail="X-User-Id header is required",
            error="missing_user_id",
        )

    try:
        user_id = int(x_user_id.strip())
    except ValueError:
        logger.warning(
            "Service-to-service call has non-integer X-User-Id",
            extra={"path": request.url.path, "x_user_id": x_user_id},
        )
        return ServiceAuthError(
            status_code=400,
            detail="X-User-Id must be a valid integer",
            error="invalid_user_id",
        )

    x_user_email = request.headers.get(HEADER_USER_EMAIL)
    if x_user_email is None or not x_user_email.strip():
        logger.warning(
            "Service-to-service call missing X-User-Email",
            extra={"path": request.url.path},
        )
        return ServiceAuthError(
            status_code=400,
            detail="X-User-Email header is required",
            error="missing_user_email",
        )

    email = x_user_email.strip()

    x_user_roles = request.headers.get(HEADER_USER_ROLES)
    x_user_permissions = request.headers.get(HEADER_USER_PERMISSIONS)
    roles = [r.strip() for r in x_user_roles.split(",") if r.strip()] if x_user_roles else []
    permissions = [p.strip() for p in x_user_permissions.split(",") if p.strip()] if x_user_permissions else []

    logger.debug(
        "Service-to-service caller authenticated",
        extra={"user_id": user_id, "path": request.url.path},
    )

    return ServiceAuthSuccess(
        user=AuthenticatedUser(
            id=user_id,
            email=email,
            roles=roles,
            permissions=permissions,
        )
    )
