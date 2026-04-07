import logging
import secrets
from typing import NoReturn, Optional
from fastapi import HTTPException, Request, status

from app.configuration.environment_variables import environment_variables
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

_HEADER_SERVICE_API_KEY = "X-Service-Api-Key"
_HEADER_USER_ID = "X-User-Id"
_HEADER_USER_EMAIL = "X-User-Email"
_HEADER_USER_ROLES = "X-User-Roles"
_HEADER_USER_PERMISSIONS = "X-User-Permissions"


class AuthenticationProvider(AuthenticationProviderInterface):
    def __init__(
            self,
            http_client: HttpClientInterface,
            authentication_provider_settings: Optional[AuthenticationProviderSettings] = None
    ) -> None:
        self._http_client = http_client
        self._settings = authentication_provider_settings or AuthenticationProviderSettings()

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

        user_id = self._parse_required_user_id(request)
        email = self._parse_required_email(request)

        logger.debug(
            "Service-to-service request authenticated successfully.",
            extra={
                "user_id": user_id,
                "path": request.url.path
            }
        )
        return self._build_authenticated_user(user_id, email, request)

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

    @staticmethod
    def _parse_required_user_id(
            request: Request
    ) -> int:
        raw_user_id = request.headers.get(_HEADER_USER_ID, "").strip()
        if not raw_user_id:
            logger.warning(
                "Service-to-service call is missing the user id header.",
                extra={
                    "path": request.url.path
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "detail": "X-User-Id header is required",
                    "error": "missing_user_id"
                }
            )

        try:
            return int(raw_user_id)
        except ValueError:
            logger.warning(
                "User id header must be a whole number.",
                extra={
                    "path": request.url.path
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "detail": "X-User-Id must be a valid integer",
                    "error": "invalid_user_id"
                }
            ) from None

    @staticmethod
    def _parse_required_email(
            request: Request
    ) -> str:
        email = request.headers.get(_HEADER_USER_EMAIL, "").strip()
        if not email:
            logger.warning(
                "Service-to-service call is missing the user email header.",
                extra={
                    "path": request.url.path
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "detail": "X-User-Email header is required",
                    "error": "missing_user_email"
                }
            )
        return email

    def _build_authenticated_user(
            self,
            user_id: int,
            email: str,
            request: Request
    ) -> AuthenticatedUser:
        return AuthenticatedUser(
            id=user_id,
            email=email,
            roles=self._parse_comma_list(request.headers.get(_HEADER_USER_ROLES)),
            permissions=self._parse_comma_list(request.headers.get(_HEADER_USER_PERMISSIONS))
        )

    async def validate_token(
            self,
            token: str
    ) -> AuthenticatedUserResponse:
        logger.debug("Validating bearer token with the authentication service.")
        try:
            response = await self._http_client.get(
                url=self._settings.authentication_url,
                headers={
                    "Authorization": self._format_bearer_token(token)
                }
            )
            authenticated_user = AuthenticatedUserResponse.model_validate(response.json())
            logger.debug(
                "Bearer token validated successfully.",
                extra={
                    "user_id": authenticated_user.id
                }
            )
            return authenticated_user

        except (
                HttpClientCircuitBreakerException,
                HttpClientConnectionException,
                HttpClientException,
                HttpClientTimeoutException
        ) as e:
            self._handle_http_error(e, operation="token validation")
            raise

        except AuthenticationProviderInvalidTokenException:
            raise

        except ValueError as e:
            logger.error("Authentication service returned a response that could not be parsed.")
            raise AuthenticationProviderInvalidTokenException("Invalid authentication response format") from e

        except Exception as e:
            logger.exception("Unexpected error while validating the bearer token.")
            raise AuthenticationProviderServiceUnavailableException("Unexpected authentication error") from e

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
    authenticated_user: Optional[AuthenticatedUser] = request.state.authenticated_user or None
    if authenticated_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )
    return authenticated_user
