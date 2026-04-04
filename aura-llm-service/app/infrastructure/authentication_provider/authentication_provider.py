import logging
from typing import NoReturn, Optional
from fastapi import HTTPException, Request, status

from app.infrastructure.authentication_provider.authentication_provider_settings import (
    AuthenticationProviderSettings
)
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.authentication_provider.exceptions.authentication_provider_exception import (
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderServiceUnavailableException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderUserNotFoundException
)
from app.infrastructure.authentication_provider.interfaces.authentication_provider_interface import (
    AuthenticationProviderInterface
)
from app.infrastructure.http_client.exceptions.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException
)
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)


class AuthenticationProvider(AuthenticationProviderInterface):
    _KNOWN_EXCEPTIONS = (
        HttpClientCircuitBreakerException,
        HttpClientConnectionException,
        HttpClientException,
        HttpClientTimeoutException
    )

    def __init__(
            self,
            http_client: HttpClientInterface,
            authentication_provider_settings: Optional[AuthenticationProviderSettings] = None
    ) -> None:
        self._http_client = http_client
        self._settings = authentication_provider_settings or AuthenticationProviderSettings()

    async def validate_token(self, token: str) -> AuthenticationResponse:
        logger.debug("Validating token")

        try:
            response = await self._http_client.get(
                url=self._settings.authentication_url,
                headers={"Authorization": self._format_bearer_token(token)}
            )
            user = self._parse_user_response(response.json())

            logger.debug(
                "Token validated successfully",
                extra={"user_id": user.id}
            )
            return user

        except self._KNOWN_EXCEPTIONS as e:
            self._handle_http_error(e, operation="token validation")

        except AuthenticationProviderInvalidTokenException:
            raise

        except ValueError as e:
            logger.error(
                "Invalid response format during token validation",
                extra={"error": str(e)}
            )
            raise AuthenticationProviderInvalidTokenException(
                "Invalid authentication response format"
            ) from e

        except Exception as e:
            logger.exception("Unexpected error during token validation")
            raise AuthenticationProviderServiceUnavailableException(
                "Unexpected authentication error"
            ) from e

    @staticmethod
    def _format_bearer_token(token: str) -> str:
        stripped = token.strip()
        if stripped.lower().startswith("bearer "):
            return stripped
        return f"Bearer {stripped}"

    @staticmethod
    def _parse_user_response(response_data: dict) -> AuthenticationResponse:
        try:
            return AuthenticationResponse(
                id=response_data["id"],
                email=response_data["email"],
                roles=response_data.get("roles", []),
                permissions=response_data.get("permissions", []),
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.error(
                "Failed to parse identity provider response",
                extra={"error": str(e)}
            )
            raise ValueError(f"Invalid user data format: {e}") from e

    def _handle_http_error(
            self,
            error: HttpClientException,
            operation: str,
    ) -> NoReturn:
        if isinstance(error, HttpClientTimeoutException):
            logger.error(
                "Timeout during authentication operation",
                extra={"operation": operation}
            )
            raise AuthenticationProviderServiceUnavailableException(
                "Authentication service timeout"
            ) from error

        if isinstance(error, HttpClientConnectionException):
            logger.error(
                "Connection error during authentication operation",
                extra={"operation": operation}
            )
            raise AuthenticationProviderServiceUnavailableException(
                "Cannot connect to authentication service"
            ) from error

        if isinstance(error, HttpClientCircuitBreakerException):
            logger.error(
                "Circuit breaker open during authentication operation",
                extra={"operation": operation}
            )
            raise AuthenticationProviderServiceUnavailableException(
                "Authentication service temporarily unavailable"
            ) from error

        status_code = getattr(error, "status_code", None)

        if status_code == 401:
            logger.warning(
                "Invalid or expired token",
                extra={"operation": operation}
            )
            raise AuthenticationProviderInvalidTokenException(
                "Invalid or expired token"
            ) from error

        if status_code == 403:
            logger.warning(
                "Access forbidden",
                extra={"operation": operation}
            )
            raise AuthenticationProviderUnauthorizedException(
                "Access forbidden"
            ) from error

        if status_code == 404:
            logger.warning(
                "User not found",
                extra={"operation": operation}
            )
            raise AuthenticationProviderUserNotFoundException(
                "User not found"
            ) from error

        logger.error(
            "Unexpected HTTP error during authentication operation",
            extra={"operation": operation, "status_code": status_code}
        )
        raise AuthenticationProviderServiceUnavailableException(
            f"Authentication service error (HTTP {status_code})"
        ) from error


async def get_authentication_provider(request: Request) -> AuthenticationProviderInterface:
    try:
        return request.app.state.authentication_provider
    except AttributeError:
        logger.error("AuthenticationProvider not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AuthenticationProvider is not available",
        )


def get_current_user(request: Request) -> AuthenticationResponse:
    user: Optional[AuthenticationResponse] = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
