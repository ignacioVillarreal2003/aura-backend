import hashlib
import logging
import secrets
from typing import Optional
import requests
from django.conf import settings
from django.core.cache import cache as _cache
from django.http import HttpRequest

from core.authentication.authenticated_user import AuthenticatedUser
from core.authentication.authentication_exceptions import (
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderServiceUnavailableException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderUserNotFoundException,
    ServiceAuthenticationRejected,
)

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "auth_token:"

_HEADER_SERVICE_API_KEY = "X-Service-Api-Key"
_HEADER_USER_ID = "X-User-Id"
_HEADER_USER_EMAIL = "X-User-Email"
_HEADER_USER_ROLES = "X-User-Roles"
_HEADER_USER_PERMISSIONS = "X-User-Permissions"


def _token_cache_ttl() -> int:
    return int(getattr(settings, "AUTH_TOKEN_CACHE_TTL_SECONDS", 60))


def _cache_key(token: str) -> str:
    return f"{_CACHE_PREFIX}{hashlib.sha256(token.encode()).hexdigest()}"


def _get_cached_user(token: str) -> Optional[AuthenticatedUser]:
    try:
        data = _cache.get(_cache_key(token))
        if data is None:
            return None
        return AuthenticatedUser(
            id=data["id"],
            email=data["email"],
            username=data.get("username", ""),
            roles=tuple(data.get("roles") or []),
            permissions=tuple(data.get("permissions") or []),
            is_super_admin=bool(data.get("is_super_admin")),
        )
    except Exception:
        logger.warning("Redis token cache read failed; falling back to auth service.", exc_info=True)
        return None


def _cache_user(token: str, user: AuthenticatedUser) -> None:
    try:
        _cache.set(
            _cache_key(token),
            {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "roles": list(user.roles),
                "permissions": list(user.permissions),
                "is_super_admin": user.is_super_admin,
            },
            timeout=_token_cache_ttl(),
        )
    except Exception:
        logger.warning("Redis token cache write failed; token will not be cached.", exc_info=True)


def _validate_url() -> str:
    base = settings.AUTHENTICATION_SERVICE_URL.rstrip("/")
    return f"{base}/auth/validate"


def _format_bearer_token(token: str) -> str:
    stripped = token.strip()
    return stripped if stripped.lower().startswith("bearer ") else f"Bearer {stripped}"


def _parse_comma_list(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class AuthenticationProvider:
    def evaluate_service_auth(self, request: HttpRequest) -> Optional[AuthenticatedUser]:
        raw_key = request.headers.get(_HEADER_SERVICE_API_KEY)
        if raw_key is None:
            return None

        api_key = raw_key.strip()
        if not api_key:
            raise ServiceAuthenticationRejected(401, "missing_service_key", "Service API key required")

        if not secrets.compare_digest(api_key, str(settings.SERVICE_API_KEY)):
            raise ServiceAuthenticationRejected(403, "invalid_service_key", "Invalid service API key")

        raw_user_id = (request.headers.get(_HEADER_USER_ID) or "").strip()
        if not raw_user_id:
            raise ServiceAuthenticationRejected(400, "missing_user_id", "X-User-Id header is required")

        try:
            user_id = int(raw_user_id)
        except ValueError:
            raise ServiceAuthenticationRejected(400, "invalid_user_id", "X-User-Id must be a valid integer")

        email = (request.headers.get(_HEADER_USER_EMAIL) or "").strip()
        if not email:
            raise ServiceAuthenticationRejected(400, "missing_user_email", "X-User-Email header is required")

        return AuthenticatedUser(
            id=user_id,
            email=email,
            roles=tuple(_parse_comma_list(request.headers.get(_HEADER_USER_ROLES))),
            permissions=tuple(_parse_comma_list(request.headers.get(_HEADER_USER_PERMISSIONS))),
        )

    def validate_token(self, token: str) -> AuthenticatedUser:
        cached = _get_cached_user(token)
        if cached is not None:
            return cached

        try:
            response = requests.get(
                _validate_url(),
                headers={"Authorization": _format_bearer_token(token)},
                timeout=10,
            )
        except requests.Timeout as exc:
            logger.error("Authentication service timed out.")
            raise AuthenticationProviderServiceUnavailableException("Authentication service timeout") from exc
        except requests.RequestException as exc:
            logger.error("Could not reach the authentication service.", exc_info=True)
            raise AuthenticationProviderServiceUnavailableException("Cannot connect to authentication service") from exc

        if response.status_code == 401:
            raise AuthenticationProviderInvalidTokenException("Invalid or expired token")
        if response.status_code == 403:
            raise AuthenticationProviderUnauthorizedException("Access forbidden")
        if response.status_code == 404:
            raise AuthenticationProviderUserNotFoundException("User not found")
        if response.status_code >= 500:
            raise AuthenticationProviderServiceUnavailableException(
                f"Authentication service error (HTTP {response.status_code})"
            )
        if response.status_code not in (200, 201):
            raise AuthenticationProviderInvalidTokenException(
                f"Unexpected authentication response (HTTP {response.status_code})"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise AuthenticationProviderInvalidTokenException("Invalid authentication response format") from exc

        try:
            user_id = int(data.get("id") or data.get("user_id"))
        except (TypeError, ValueError) as exc:
            raise AuthenticationProviderInvalidTokenException("Invalid authentication response format") from exc

        user = AuthenticatedUser(
            id=user_id,
            email=str(data.get("email", "")),
            username=str(data.get("username", "")),
            roles=tuple(data.get("roles") or []),
            permissions=tuple(data.get("permissions") or []),
            is_super_admin=bool(
                data.get("is_super_admin")
                or "SUPERADMIN" in (data.get("roles") or [])
                or "superadmin" in (data.get("roles") or [])
            ),
        )
        _cache_user(token, user)
        return user


authentication_provider = AuthenticationProvider()
