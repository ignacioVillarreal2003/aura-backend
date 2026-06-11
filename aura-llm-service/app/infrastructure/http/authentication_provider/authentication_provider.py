import hashlib
import json
import logging
import secrets
from typing import NoReturn, Optional
from pydantic import ValidationError
from fastapi import HTTPException, Request, status

from app.configuration.environment_variables import environment_variables
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.types import UserId
from app.infrastructure.http.authentication_provider.authentication_provider_settings import (
    AuthenticationProviderSettings
)
from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import (
    AuthenticatedUserResponse
)
from app.infrastructure.http.authentication_provider.exceptions.authentication_provider_exception import (
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderServiceUnavailableException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderUserNotFoundException
)
from app.infrastructure.http.authentication_provider.interfaces.authentication_provider_interface import (
    AuthenticationProviderInterface,
)
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException
)
from app.infrastructure.http.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "auth_token:"


def _cache_key(token: str) -> str:
    return f"{_CACHE_PREFIX}{hashlib.sha256(token.encode()).hexdigest()}"


async def _get_cached_user(redis_client, token: str) -> Optional[AuthenticatedUserResponse]:
    try:
        raw = await redis_client.get(_cache_key(token))
        if raw is None:
            return None
        return AuthenticatedUserResponse.model_validate(json.loads(raw))
    except Exception:
        logger.warning("Redis token cache read failed; falling back to auth service.", exc_info=True)
        return None


async def _cache_user(redis_client, token: str, user: AuthenticatedUserResponse, ttl: int) -> None:
    try:
        await redis_client.setex(
            _cache_key(token),
            ttl,
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
_HEADER_SERVICE_USER_ID = "X-User-Id"
_HEADER_SERVICE_USER_EMAIL = "X-User-Email"
_HEADER_SERVICE_USER_ROLES = "X-User-Roles"
_HEADER_SERVICE_USER_PERMISSIONS = "X-User-Permissions"


class AuthenticationProvider(AuthenticationProviderInterface):
    def __init__(
            self,
            http_client: HttpClientInterface,
            authentication_provider_settings: Optional[AuthenticationProviderSettings] = None,
            redis_client=None,
    ) -> None:
        self._http_client = http_client
        self._settings = authentication_provider_settings or AuthenticationProviderSettings()
        self._redis_client = redis_client

    def evaluate_service_auth(
            self,
            request: Request
    ) -> Optional[AuthenticatedUser]:
        raw_key = self._read_optional_service_api_key(request)
        if raw_key is None:
            return None

        api_key = raw_key.strip()
        self._require_non_empty_service_api_key(request, api_key)
        self._assert_service_api_key_valid(request, api_key)

        authenticated_user = self._resolve_service_user(request)
        logger.debug(
            "Service-to-service request authenticated.",
            extra={"path": request.url.path, "user_id": authenticated_user.id},
        )
        return authenticated_user

    def _resolve_service_user(
            self,
            request: Request
    ) -> AuthenticatedUser:
        # Internal services act on behalf of the end user that triggered the
        # work (e.g. document ingestion), so the user's identity, roles and
        # permissions must be forwarded in X-User-* headers. There is no
        # anonymous service identity: permission-protected endpoints need the
        # real user to authorize and rate-limit correctly.
        raw_user_id = (request.headers.get(_HEADER_SERVICE_USER_ID) or "").strip()
        if not raw_user_id:
            self._reject_service_user_headers(
                request,
                reason="missing_user_id",
                detail="X-User-Id header is required for service requests",
            )

        try:
            user_id = int(raw_user_id)
            if user_id <= 0:
                raise ValueError("user id must be positive")
        except ValueError:
            self._reject_service_user_headers(
                request,
                reason="invalid_user_id",
                detail="X-User-Id header must be a positive integer",
            )

        email = (request.headers.get(_HEADER_SERVICE_USER_EMAIL) or "").strip()
        if not email:
            self._reject_service_user_headers(
                request,
                reason="missing_user_email",
                detail="X-User-Email header is required for service requests",
            )
        if len(email) > self._settings.max_service_user_email_length:
            self._reject_service_user_headers(
                request,
                reason="user_email_too_long",
                detail="X-User-Email header exceeds the configured maximum length",
            )

        roles_header = request.headers.get(_HEADER_SERVICE_USER_ROLES)
        if roles_header and len(roles_header) > self._settings.max_service_roles_header_characters:
            self._reject_service_user_headers(
                request,
                reason="roles_header_too_long",
                detail="X-User-Roles header exceeds the configured maximum length",
            )

        permissions_header = request.headers.get(_HEADER_SERVICE_USER_PERMISSIONS)
        if permissions_header and len(permissions_header) > self._settings.max_service_permissions_header_characters:
            self._reject_service_user_headers(
                request,
                reason="permissions_header_too_long",
                detail="X-User-Permissions header exceeds the configured maximum length",
            )

        return AuthenticatedUser(
            id=UserId(user_id),
            email=email,
            roles=self._parse_comma_list(roles_header),
            permissions=self._parse_comma_list(permissions_header),
        )

    @staticmethod
    def _reject_service_user_headers(
            request: Request,
            reason: str,
            detail: str,
    ) -> NoReturn:
        logger.warning(
            "Service-to-service request carries missing or invalid X-User-* headers.",
            extra={"path": request.url.path, "error_code": reason},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": detail,
                "error": reason,
            },
        )

    @staticmethod
    def _read_optional_service_api_key(
            request: Request
    ) -> Optional[str]:
        return request.headers.get(_HEADER_SERVICE_API_KEY)

    @staticmethod
    def _require_non_empty_service_api_key(
            request: Request,
            api_key: str
    ) -> None:
        if not api_key:
            logger.warning(
                "Service API key header was present but empty.",
                extra={
                    "path": request.url.path
                }
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "detail": "Service API key required",
                    "error": "missing_service_key"
                }
            )

    @staticmethod
    def _assert_service_api_key_valid(
            request: Request,
            api_key: str
    ) -> None:
        if not secrets.compare_digest(api_key, environment_variables.service_api_key):
            logger.warning(
                "Service API key does not match the configured value.",
                extra={
                    "path": request.url.path
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "detail": "Invalid service API key",
                    "error": "invalid_service_key"
                }
            )

    async def validate_token(
            self,
            token: str
    ) -> AuthenticatedUserResponse:
        stripped = token.strip()
        if len(stripped) > self._settings.max_bearer_token_characters:
            logger.warning(
                "Rejected a bearer token that exceeds the configured maximum length.",
                extra={"error_code": "token_too_long"},
            )
            raise AuthenticationProviderInvalidTokenException("Bearer token is too long.")

        if self._redis_client is not None:
            cached = await _get_cached_user(self._redis_client, stripped)
            if cached is not None:
                logger.debug(
                    "Bearer token resolved from cache.",
                    extra={"user_id": cached.id}
                )
                return cached

        logger.debug("Validating bearer token with the authentication service.")
        try:
            response = await self._http_client.get(
                url=self._settings.authentication_url,
                headers={
                    "Authorization": self._format_bearer_token(stripped),
                    "Accept": "application/json",
                },
                timeout=self._settings.request_timeout_seconds,
            )
        except (
                HttpClientCircuitBreakerException,
                HttpClientConnectionException,
                HttpClientException,
                HttpClientTimeoutException
        ) as e:
            self._handle_http_error(e, operation="token validation")
            raise

        try:
            payload = response.json()
        except json.JSONDecodeError as e:
            logger.error(
                "Authentication service returned a response that is not valid JSON.",
                extra={
                    "operation": "token validation",
                    "reason": "invalid_json",
                },
            )
            raise AuthenticationProviderInvalidTokenException(
                "Invalid authentication response format",
            ) from e

        try:
            authenticated_user = AuthenticatedUserResponse.model_validate(payload)
        except ValidationError as e:
            logger.error(
                "Authentication service returned a response that failed schema validation.",
                extra={
                    "operation": "token validation",
                    "reason": "response_validation_failed",
                    "validation_error_count": len(e.errors()),
                },
            )
            raise AuthenticationProviderServiceUnavailableException(
                "Unexpected authentication response shape",
            ) from e

        if self._redis_client is not None:
            await _cache_user(
                self._redis_client,
                stripped,
                authenticated_user,
                self._settings.token_cache_ttl_seconds,
            )

        logger.debug(
            "Bearer token validated successfully.",
            extra={"user_id": authenticated_user.id}
        )
        return authenticated_user

    @staticmethod
    def _format_bearer_token(
            token: str
    ) -> str:
        stripped = token.strip()
        return stripped if stripped.lower().startswith("bearer ") else f"Bearer {stripped}"

    @staticmethod
    def _parse_comma_list(
            value: Optional[str]
    ) -> list[str]:
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    def _handle_http_error(
            self,
            error: HttpClientException,
            operation: str
    ) -> NoReturn:
        if isinstance(error, HttpClientTimeoutException):
            logger.error(
                "Authentication service timed out.",
                extra={
                    "operation": operation
                }
            )
            raise AuthenticationProviderServiceUnavailableException("Authentication service timeout") from error

        if isinstance(error, HttpClientConnectionException):
            logger.error(
                "Could not connect to the authentication service.",
                extra={
                    "operation": operation
                }
            )
            raise AuthenticationProviderServiceUnavailableException(
                "Cannot connect to authentication service"
            ) from error

        if isinstance(error, HttpClientCircuitBreakerException):
            logger.error(
                "Authentication service is temporarily unavailable.",
                extra={
                    "operation": operation
                }
            )
            raise AuthenticationProviderServiceUnavailableException(
                "Authentication service temporarily unavailable"
            ) from error

        status_code = getattr(error, "status_code", None)
        if status_code == 401:
            logger.warning(
                "Authentication service rejected the token as invalid or expired.",
                extra={
                    "operation": operation
                }
            )
            raise AuthenticationProviderInvalidTokenException("Invalid or expired token") from error
        if status_code == 403:
            logger.warning(
                "Authentication service denied access for this token.",
                extra={
                    "operation": operation
                }
            )
            raise AuthenticationProviderUnauthorizedException("Access forbidden") from error
        if status_code == 404:
            logger.warning(
                "Authentication service reported that the user was not found.",
                extra={
                    "operation": operation
                }
            )
            raise AuthenticationProviderUserNotFoundException("User not found") from error

        logger.error(
            "Authentication service returned an unexpected error response.",
            extra={
                "operation": operation,
                "status_code": status_code
            }
        )
        raise AuthenticationProviderServiceUnavailableException(
            f"Authentication service error (HTTP {status_code})"
        ) from error


def get_authenticated_user(
        request: Request
) -> AuthenticatedUser:
    authenticated_user: Optional[AuthenticatedUser] = getattr(request.state, "authenticated_user", None)
    if authenticated_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )
    return authenticated_user
