import hashlib
import json
import logging
import secrets
import threading
from functools import lru_cache
from typing import Optional
import httpx
import redis
from django.conf import settings
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


_HEADER_SERVICE_API_KEY = "X-Service-Api-Key"
_HEADER_USER_ID = "X-User-Id"
_HEADER_USER_EMAIL = "X-User-Email"

_SERVICE_PRINCIPAL_ID = 0
_SERVICE_PRINCIPAL_EMAIL = "service@internal"


def _service_principal_permissions() -> tuple[str, ...]:
    raw = getattr(settings, "SERVICE_API_PRINCIPAL_PERMISSIONS", "*")
    if isinstance(raw, (list, tuple)):
        items = [str(p).strip() for p in raw if str(p).strip()]
    else:
        items = [p.strip() for p in str(raw).split(",") if p.strip()]
    return tuple(items) or ("*",)


def _service_principal_roles() -> tuple[str, ...]:
    raw = getattr(settings, "SERVICE_API_PRINCIPAL_ROLES", "SERVICE")
    if isinstance(raw, (list, tuple)):
        items = [str(r).strip() for r in raw if str(r).strip()]
    else:
        items = [r.strip() for r in str(raw).split(",") if r.strip()]
    return tuple(items) or ("SERVICE",)


def build_service_user_headers(authenticated_user: Optional[AuthenticatedUser] = None) -> dict[str, str]:
    """Headers for an outbound inter-service call.

    Preferred path: forward the caller's bearer token so the downstream service
    validates it (shared token cache / auth service) and acts with the real
    user's permissions. Fallback (no token in context — e.g. background/system
    work): the service API key, with the user id/email only as audit context.
    Permission/role trust headers are intentionally no longer sent: a valid
    service key already implies full internal trust.
    """
    from core.authentication.request_token import get_request_token

    token = get_request_token()
    if token:
        return {"Authorization": _format_bearer_token(token)}

    headers: dict[str, str] = {_HEADER_SERVICE_API_KEY: str(settings.SERVICE_API_KEY)}
    if authenticated_user is not None:
        headers[_HEADER_USER_ID] = str(authenticated_user.id)
        headers[_HEADER_USER_EMAIL] = str(authenticated_user.email)
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

        # A valid service key implies full internal trust → system principal.
        # We no longer read the self-asserted X-User-Roles / X-User-Permissions
        # headers; X-User-Id / X-User-Email are accepted only as optional audit
        # context (token-less background/system calls may omit them).
        raw_user_id = (request.headers.get(_HEADER_USER_ID) or "").strip()
        try:
            user_id = int(raw_user_id) if raw_user_id else _SERVICE_PRINCIPAL_ID
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

        email = (request.headers.get(_HEADER_USER_EMAIL) or "").strip() or _SERVICE_PRINCIPAL_EMAIL

        logger.debug(
            "Service-to-service request authenticated as system principal.",
            extra={"user_id": user_id, "path": request.path},
        )
        return AuthenticatedUser(
            id=user_id,
            email=email,
            roles=_service_principal_roles(),
            permissions=_service_principal_permissions(),
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
