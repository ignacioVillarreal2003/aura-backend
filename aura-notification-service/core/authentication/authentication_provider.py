"""Authentication provider used by the AuthenticationMiddleware.

Resolves bearer tokens against the central authentication service
(`/auth/validate`) and additionally accepts trusted service-to-service
calls through the `X-Service-Api-Key` + `X-User-Id`/`X-User-Email`
header set, mirroring the convention used by the other Aura services.
"""

import hashlib
import logging
import secrets
import threading
import time
from typing import Optional

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

_TOKEN_CACHE_MAX_SIZE = 2000
_token_cache: dict[str, tuple[AuthenticatedUser, float]] = {}
_token_cache_lock = threading.Lock()

_HEADER_SERVICE_API_KEY = "X-Service-Api-Key"
_HEADER_USER_ID = "X-User-Id"
_HEADER_USER_EMAIL = "X-User-Email"
_HEADER_USER_ROLES = "X-User-Roles"
_HEADER_USER_PERMISSIONS = "X-User-Permissions"


def _token_cache_ttl() -> float:
    return float(getattr(settings, "AUTH_TOKEN_CACHE_TTL_SECONDS", 60))


def _cache_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _get_cached_user(token: str) -> Optional[AuthenticatedUser]:
    key = _cache_key(token)
    with _token_cache_lock:
        entry = _token_cache.get(key)
        if entry is None:
            return None
        user, expires_at = entry
        if time.monotonic() >= expires_at:
            del _token_cache[key]
            return None
        return user


def _cache_user(token: str, user: AuthenticatedUser) -> None:
    key = _cache_key(token)
    expires_at = time.monotonic() + _token_cache_ttl()
    with _token_cache_lock:
        if len(_token_cache) >= _TOKEN_CACHE_MAX_SIZE:
            now = time.monotonic()
            expired = [k for k, (_, exp) in _token_cache.items() if exp <= now]
            for k in expired:
                del _token_cache[k]
            if len(_token_cache) >= _TOKEN_CACHE_MAX_SIZE:
                oldest = min(_token_cache, key=lambda k: _token_cache[k][1])
                del _token_cache[oldest]
        _token_cache[key] = (user, expires_at)


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
            logger.error("Could not reach the authentication service: %s", exc)
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
