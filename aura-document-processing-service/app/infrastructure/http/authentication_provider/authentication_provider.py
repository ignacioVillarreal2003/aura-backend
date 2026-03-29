import logging
import secrets
from typing import NoReturn, Optional
from fastapi import HTTPException, Request, status

from app.domain.models.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.authentication_provider_settings import (
    AuthenticationProviderSettings,
)
from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import (
    AuthenticatedUserResponse,
)
from app.infrastructure.http.authentication_provider.exceptions.authentication_provider_exception import (
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderServiceUnavailableException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderUserNotFoundException,
)
from app.infrastructure.http.authentication_provider.interfaces.authentication_provider_interface import (
    AuthenticationProviderInterface,
)
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException,
)
from app.infrastructure.http.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)


class AuthenticationProvider(AuthenticationProviderInterface):
    HEADER_SERVICE_API_KEY  = "X-Service-Api-Key"
    HEADER_USER_ID          = "X-User-Id"
    HEADER_USER_EMAIL       = "X-User-Email"
    HEADER_USER_ROLES       = "X-User-Roles"
    HEADER_USER_PERMISSIONS = "X-User-Permissions"

    _KNOWN_HTTP_EXCEPTIONS = (
        HttpClientCircuitBreakerException,
        HttpClientConnectionException,
        HttpClientException,
        HttpClientTimeoutException,
    )

    def __init__(
        self,
        http_client: HttpClientInterface,
        settings: Optional[AuthenticationProviderSettings] = None,
    ) -> None:
        self._http_client = http_client
        self._settings = settings or AuthenticationProviderSettings()

    def evaluate_service_auth(self, request: Request) -> Optional[AuthenticatedUser]:
        raw_key = request.headers.get(self.HEADER_SERVICE_API_KEY)
        if raw_key is None:
            return None

        api_key = raw_key.strip()
        if not api_key:
            logger.warning("S2S auth: empty X-Service-Api-Key", extra={"path": request.url.path})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"detail": "Service API key required", "error": "missing_service_key"},
            )

        if not secrets.compare_digest(api_key, self._settings.internal_service_api_key):
            logger.warning("S2S auth: invalid X-Service-Api-Key", extra={"path": request.url.path})
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"detail": "Invalid service API key", "error": "invalid_service_key"},
            )

        raw_user_id = request.headers.get(self.HEADER_USER_ID, "").strip()
        if not raw_user_id:
            logger.warning("S2S auth: missing X-User-Id", extra={"path": request.url.path})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "X-User-Id header is required", "error": "missing_user_id"},
            )

        try:
            user_id = int(raw_user_id)
        except ValueError:
            logger.warning("S2S auth: non-integer X-User-Id", extra={"path": request.url.path, "value": raw_user_id})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "X-User-Id must be a valid integer", "error": "invalid_user_id"},
            )

        email = request.headers.get(self.HEADER_USER_EMAIL, "").strip()
        if not email:
            logger.warning("S2S auth: missing X-User-Email", extra={"path": request.url.path})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "X-User-Email header is required", "error": "missing_user_email"},
            )

        logger.debug("S2S auth: accepted", extra={"user_id": user_id, "path": request.url.path})
        return AuthenticatedUser(
            id=user_id,
            email=email,
            roles=self._parse_comma_list(request.headers.get(self.HEADER_USER_ROLES)),
            permissions=self._parse_comma_list(request.headers.get(self.HEADER_USER_PERMISSIONS)),
        )

    async def validate_token(self, token: str) -> AuthenticatedUserResponse:
        logger.debug("Validating JWT token")
        try:
            response = await self._http_client.get(
                url=self._settings.authentication_url,
                headers={"Authorization": self._format_bearer_token(token)},
            )
            authenticated_user = AuthenticatedUserResponse.model_validate(response.json())
            logger.debug("JWT token valid", extra={"user_id": authenticated_user.id})
            return authenticated_user

        except self._KNOWN_HTTP_EXCEPTIONS as e:
            self._handle_http_error(e, operation="token validation")

        except AuthenticationProviderInvalidTokenException:
            raise

        except ValueError as e:
            logger.error("Invalid auth response format", extra={"error": str(e)})
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
        return stripped if stripped.lower().startswith("bearer ") else f"Bearer {stripped}"

    @staticmethod
    def _parse_comma_list(value: Optional[str]) -> list[str]:
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    def _handle_http_error(self, error: HttpClientException, operation: str) -> NoReturn:
        if isinstance(error, HttpClientTimeoutException):
            logger.error("Auth timeout", extra={"operation": operation})
            raise AuthenticationProviderServiceUnavailableException(
                "Authentication service timeout"
            ) from error

        if isinstance(error, HttpClientConnectionException):
            logger.error("Auth connection error", extra={"operation": operation})
            raise AuthenticationProviderServiceUnavailableException(
                "Cannot connect to authentication service"
            ) from error

        if isinstance(error, HttpClientCircuitBreakerException):
            logger.error("Auth circuit breaker open", extra={"operation": operation})
            raise AuthenticationProviderServiceUnavailableException(
                "Authentication service temporarily unavailable"
            ) from error

        status_code = getattr(error, "status_code", None)
        if status_code == 401:
            logger.warning("Invalid/expired token", extra={"operation": operation})
            raise AuthenticationProviderInvalidTokenException("Invalid or expired token") from error
        if status_code == 403:
            logger.warning("Access forbidden", extra={"operation": operation})
            raise AuthenticationProviderUnauthorizedException("Access forbidden") from error
        if status_code == 404:
            logger.warning("User not found", extra={"operation": operation})
            raise AuthenticationProviderUserNotFoundException("User not found") from error

        logger.error("Unexpected HTTP error", extra={"operation": operation, "status_code": status_code})
        raise AuthenticationProviderServiceUnavailableException(
            f"Authentication service error (HTTP {status_code})"
        ) from error


def get_authenticated_user(request: Request) -> AuthenticatedUser:
    user: Optional[AuthenticatedUser] = getattr(request.state, "authenticated_user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
