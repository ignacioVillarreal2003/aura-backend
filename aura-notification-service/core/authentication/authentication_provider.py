import hashlib
import json
import logging
import secrets
from functools import lru_cache
from typing import Optional
import redis
import requests
from django.conf import settings
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


@lru_cache(maxsize=1)
def _token_cache_redis() -> redis.Redis:
    # Raw Redis client (literal key, JSON value) so the validated-token cache is
    # shared cross-stack with the FastAPI services, which write the same
    # `auth_token:<sha256>` key. Django's default cache would prepend a
    # KEY_PREFIX/version and break sharing.
    url = getattr(settings, "AUTH_TOKEN_CACHE_REDIS_URL", "") or settings.REDIS_URL
    return redis.Redis.from_url(url, decode_responses=True)


def _get_cached_user(token: str) -> Optional[AuthenticatedUser]:
    try:
        raw = _token_cache_redis().get(_cache_key(token))
        if raw is None:
            return None
        data = json.loads(raw)
        return AuthenticatedUser(
            id=data["id"],
            email=data["email"],
            username=data.get("username", ""),
            roles=tuple(data.get("roles") or []),
            permissions=tuple(data.get("permissions") or []),
        )
    except Exception:
        logger.warning("Redis token cache read failed; falling back to auth service.", exc_info=True)
        return None


def _cache_user(token: str, user: AuthenticatedUser) -> None:
    try:
        _token_cache_redis().setex(
            _cache_key(token),
            _token_cache_ttl(),
            json.dumps({
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "roles": list(user.roles),
                "permissions": list(user.permissions),
            }),
        )
    except Exception:
        logger.warning("Redis token cache write failed; token will not be cached.", exc_info=True)


def _validate_url() -> str:
    return settings.AUTHENTICATION_SERVICE_URL.rstrip("/")


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

        # Gateway "on-behalf-of-user" model: the service key authenticates the
        # caller (a trusted internal service) and the X-User-* headers carry the
        # impersonated end user, whose permissions are then enforced normally.
        raw_user_id = request.headers.get(_HEADER_USER_ID)
        if not raw_user_id or not raw_user_id.strip():
            raise ServiceAuthenticationRejected(400, "missing_user_id", "X-User-Id header required")
        try:
            user_id = int(raw_user_id.strip())
        except (TypeError, ValueError):
            raise ServiceAuthenticationRejected(400, "invalid_user_id", "X-User-Id must be an integer")

        email = request.headers.get(_HEADER_USER_EMAIL)
        if not email or not email.strip():
            raise ServiceAuthenticationRejected(400, "missing_user_email", "X-User-Email header required")

        roles = tuple(_parse_comma_list(request.headers.get(_HEADER_USER_ROLES)))
        permissions = tuple(_parse_comma_list(request.headers.get(_HEADER_USER_PERMISSIONS)))

        logger.debug("Service-to-service request authenticated.", extra={"path": request.path})
        return AuthenticatedUser(
            id=user_id,
            email=email.strip(),
            roles=roles,
            permissions=permissions,
            is_service=False,
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
        )
        _cache_user(token, user)
        return user


authentication_provider = AuthenticationProvider()
