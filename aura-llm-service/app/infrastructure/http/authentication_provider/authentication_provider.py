import hashlib
import json
import logging
from typing import NoReturn, Optional
from pydantic import ValidationError
from fastapi import HTTPException, Request, status

from app.domain.authentication.authenticated_user import AuthenticatedUser
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
