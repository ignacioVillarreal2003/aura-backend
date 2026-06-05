import hashlib
import logging
import secrets
import threading
from typing import Optional
import httpx
from django.conf import settings
from django.core.cache import cache as _cache
from django.http import HttpRequest

from core.authentication.authenticated_user import AuthenticatedUser
from core.authentication.authentication_exceptions import (
    AuthenticationProviderException,
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderServiceUnavailableException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderUserNotFoundException,
    ServiceAuthenticationRejected,
)

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "auth_token:"

_auth_http_client: httpx.Client | None = None
_auth_http_client_lock = threading.Lock()


def _get_auth_http_client() -> httpx.Client:
    global _auth_http_client
    if _auth_http_client is not None:
        return _auth_http_client
    with _auth_http_client_lock:
        if _auth_http_client is None:
            # Keep this timeout aggressive (default 5 s). This client runs in
            # Django's sync thread pool under Daphne; a slow auth service
            # exhausts threads for all concurrent requests.
            timeout = float(getattr(settings, "AUTH_SERVICE_TIMEOUT", 5.0))
            _auth_http_client = httpx.Client(
                timeout=httpx.Timeout(
                    connect=min(timeout, 3.0),
                    read=timeout,
                    write=timeout,
                    pool=timeout,
                ),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
    return _auth_http_client


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
            },
            timeout=_token_cache_ttl(),
        )
    except Exception:
        logger.warning("Redis token cache write failed; token will not be cached.", exc_info=True)


_HEADER_SERVICE_API_KEY = "X-Service-Api-Key"
_HEADER_USER_ID = "X-User-Id"
_HEADER_USER_EMAIL = "X-User-Email"
_HEADER_USER_ROLES = "X-User-Roles"
_HEADER_USER_PERMISSIONS = "X-User-Permissions"


def build_service_user_headers(authenticated_user: Optional[AuthenticatedUser] = None) -> dict[str, str]:
    headers: dict[str, str] = {_HEADER_SERVICE_API_KEY: str(settings.SERVICE_API_KEY)}
    if authenticated_user is not None:
        headers[_HEADER_USER_ID] = str(authenticated_user.id)
        headers[_HEADER_USER_EMAIL] = str(authenticated_user.email)
        headers[_HEADER_USER_ROLES] = ",".join(authenticated_user.roles)
        headers[_HEADER_USER_PERMISSIONS] = ",".join(authenticated_user.permissions)
    return headers


class AuthenticationProvider:
    def evaluate_service_auth(self, request: HttpRequest) -> Optional[AuthenticatedUser]:
        raw_key = request.headers.get(_HEADER_SERVICE_API_KEY)
        if raw_key is None:
            return None

        api_key = raw_key.strip()
        if not api_key:
            logger.warning(
                "Service API key header was present but empty.",
                extra={"path": request.path},
            )
            raise ServiceAuthenticationRejected(
                401,
                "missing_service_key",
                "Service API key required",
            )

        if not secrets.compare_digest(api_key, settings.SERVICE_API_KEY):
            logger.warning(
                "Service API key does not match the configured value.",
                extra={"path": request.path},
            )
            raise ServiceAuthenticationRejected(
                403,
                "invalid_service_key",
                "Invalid service API key",
            )

        raw_user_id = (request.headers.get(_HEADER_USER_ID) or "").strip()
        if not raw_user_id:
            logger.warning(
                "Service-to-service call is missing the user id header.",
                extra={"path": request.path},
            )
            raise ServiceAuthenticationRejected(
                400,
                "missing_user_id",
                "X-User-Id header is required",
            )

        try:
            user_id = int(raw_user_id)
        except ValueError:
            logger.warning(
                "User id header must be a whole number.",
                extra={"path": request.path},
            )
            raise ServiceAuthenticationRejected(
                400,
                "invalid_user_id",
                "X-User-Id must be a valid integer",
            )

        email = (request.headers.get(_HEADER_USER_EMAIL) or "").strip()
        if not email:
            logger.warning(
                "Service-to-service call is missing the user email header.",
                extra={"path": request.path},
            )
            raise ServiceAuthenticationRejected(
                400,
                "missing_user_email",
                "X-User-Email header is required",
            )

        logger.debug(
            "Service-to-service request authenticated successfully.",
            extra={"user_id": user_id, "path": request.path},
        )
        return AuthenticatedUser(
            id=user_id,
            email=email,
            roles=tuple(_parse_comma_list(request.headers.get(_HEADER_USER_ROLES))),
            permissions=tuple(_parse_comma_list(request.headers.get(_HEADER_USER_PERMISSIONS))),
        )

    def validate_token(self, token: str) -> AuthenticatedUser:
        cached = _get_cached_user(token)
        if cached is not None:
            logger.debug("Token resolved from cache.", extra={"user_id": cached.id})
            return cached

        logger.debug("Validating bearer token with the authentication service.")
        auth_header = _format_bearer_token(token)

        try:
            response = _get_auth_http_client().get(
                settings.AUTHENTICATION_SERVICE_URL,
                headers={"Authorization": auth_header},
            )
        except httpx.TimeoutException as e:
            logger.error("Authentication service timed out.")
            raise AuthenticationProviderServiceUnavailableException(
                "Authentication service timeout"
            ) from e
        except httpx.RequestError as e:
            logger.error("Could not connect to the authentication service.")
            raise AuthenticationProviderServiceUnavailableException(
                "Cannot connect to authentication service"
            ) from e

        if response.status_code == 401:
            logger.warning("Authentication service rejected the token as invalid or expired.")
            raise AuthenticationProviderInvalidTokenException("Invalid or expired token")
        if response.status_code == 403:
            logger.warning("Authentication service denied access for this token.")
            raise AuthenticationProviderUnauthorizedException("Access forbidden")
        if response.status_code == 404:
            logger.warning("Authentication service reported that the user was not found.")
            raise AuthenticationProviderUserNotFoundException("User not found")
        if response.status_code >= 500:
            logger.error(
                "Authentication service returned an unexpected error response.",
                extra={"status_code": response.status_code},
            )
            raise AuthenticationProviderServiceUnavailableException(
                f"Authentication service error (HTTP {response.status_code})"
            )

        try:
            data = response.json()
        except ValueError as e:
            logger.error("Authentication service returned a response that could not be parsed.")
            raise AuthenticationProviderInvalidTokenException(
                "Invalid authentication response format"
            ) from e

        try:
            user_id = int(data["id"])
        except (KeyError, TypeError, ValueError) as e:
            logger.error("Authentication response missing valid user id.")
            raise AuthenticationProviderInvalidTokenException(
                "Invalid authentication response format"
            ) from e

        user = AuthenticatedUser(
            id=user_id,
            email=str(data.get("email", "")),
            username=str(data.get("username", "")),
            roles=tuple(data.get("roles") or []),
            permissions=tuple(data.get("permissions") or []),
        )
        _cache_user(token, user)
        return user


def _format_bearer_token(token: str) -> str:
    stripped = token.strip()
    return stripped if stripped.lower().startswith("bearer ") else f"Bearer {stripped}"


def _parse_comma_list(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


authentication_provider = AuthenticationProvider()
