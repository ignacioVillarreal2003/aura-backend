import logging
from typing import NoReturn, Optional
from fastapi import HTTPException, Request, status

from app.domain.models.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.authentication_provider_settings import (
    AuthenticationProviderSettings
)
from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import AuthenticatedUserResponse
from app.infrastructure.http.authentication_provider.exceptions.authentication_provider_exception import (
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderServiceUnavailableException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderUserNotFoundException
)
from app.infrastructure.http.authentication_provider.interfaces.authentication_provider_interface import (
    AuthenticationProviderInterface
)
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException
)
from app.infrastructure.http.http_client.interfaces.http_client_interface import HttpClientInterface

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

    async def validate_token(self, token: str) -> AuthenticatedUserResponse:
        logger.debug("Validating token")

        try:
            response = await self._http_client.get(
                url=self._settings.authentication_url,
                headers={"Authorization": self._format_bearer_token(token)}
            )
            authenticated_user = AuthenticatedUserResponse.model_validate(
                response.json()
            )

            logger.debug(
                "Token validated successfully",
                extra={"user_id": authenticated_user.id}
            )
            return authenticated_user

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


def get_authenticated_user(request: Request) -> AuthenticatedUser:
    authenticated_user: Optional[AuthenticatedUser] = getattr(request.state, "authenticated_user", None)
    if authenticated_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authenticated_user
