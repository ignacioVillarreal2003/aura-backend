import logging
from typing import List, Dict, Any, Optional

from app.infrastructure.authentication_provider.dtos.authentication_response import (
    AuthenticationResponse
)
from app.infrastructure.authentication_provider.exceptions.authentication_provider_exception import (
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderUserNotFoundException,
    AuthenticationProviderInsufficientPermissionsException,
    AuthenticationProviderServiceUnavailableException
)
from app.infrastructure.authentication_provider.interfaces.authentication_provider_interface import (
    AuthenticationProviderInterface
)
from app.infrastructure.http_client.exceptions.http_client_exceptions import (
    HttpClientTimeoutException,
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException
)
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)


class AuthenticationProvider(AuthenticationProviderInterface):
    def __init__(
            self,
            http_client: HttpClientInterface,
            authentication_validate_token_url: str,
            authentication_verify_permissions_url: str,
            authentication_get_user_by_token_url: str
    ):
        self._http_client = http_client
        self._authentication_validate_token_url = authentication_validate_token_url.rstrip('/')
        self._authentication_verify_permissions_url = authentication_verify_permissions_url.rstrip('/')
        self._authentication_get_user_by_token_url = authentication_get_user_by_token_url.rstrip('/')

        self._token_validations = 0
        self._permission_checks = 0
        self._user_retrievals = 0
        self._successful_operations = 0
        self._failed_operations = 0
        self._invalid_tokens = 0
        self._permission_denials = 0
        self._last_health_check: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
            cls,
            http_client: HttpClientInterface,
            authentication_validate_token_url: str,
            authentication_verify_permissions_url: str,
            authentication_get_user_by_token_url: str
    ) -> "AuthenticationProvider":
        return cls(
            http_client=http_client,
            authentication_validate_token_url=authentication_validate_token_url,
            authentication_verify_permissions_url=authentication_verify_permissions_url,
            authentication_get_user_by_token_url=authentication_get_user_by_token_url
        )

    def _format_token(
            self,
            token: str
    ) -> str:
        token = token.strip()
        if not token.lower().startswith('bearer '):
            return f"Bearer {token}"
        return token

    def _parse_user_response(
            self,
            response_data: dict
    ) -> AuthenticationResponse:
        try:
            return AuthenticationResponse(
                id=response_data.get("id"),
                email=response_data.get("email"),
                username=response_data.get("username"),
                roles=response_data.get("roles", [])
            )
        except Exception as e:
            logger.error(f"Failed to parse user response: {e}")
            raise ValueError(f"Invalid user data format: {e}") from e

    def _handle_http_error(
            self,
            error: Exception,
            operation: str
    ) -> None:
        if isinstance(error, HttpClientTimeoutException):
            logger.error(f"Timeout during {operation}: {error}")
            raise AuthenticationProviderServiceUnavailableException("Authentication service timeout") from error

        elif isinstance(error, HttpClientConnectionException):
            logger.error(f"Connection error during {operation}: {error}")
            raise AuthenticationProviderServiceUnavailableException(
                "Cannot connect to authentication service") from error

        elif isinstance(error, HttpClientCircuitBreakerException):
            logger.error(f"Circuit breaker open during {operation}: {error}")
            raise AuthenticationProviderServiceUnavailableException(
                "Authentication service temporarily unavailable") from error

        elif isinstance(error, HttpClientException):
            error_message = str(error)

            if "401" in error_message or "Unauthorized" in error_message:
                logger.warning(f"Invalid token during {operation}")
                self._invalid_tokens += 1
                raise AuthenticationProviderInvalidTokenException("Invalid or expired token") from error

            elif "403" in error_message or "Forbidden" in error_message:
                logger.warning(f"Access forbidden during {operation}")
                self._permission_denials += 1
                raise AuthenticationProviderUnauthorizedException("Access forbidden") from error

            elif "404" in error_message or "Not Found" in error_message:
                logger.warning(f"User not found during {operation}")
                raise AuthenticationProviderUserNotFoundException("User not found") from error

            else:
                logger.error(f"HTTP error during {operation}: {error}")
                raise AuthenticationProviderServiceUnavailableException(
                    f"Authentication service error: {error_message}") from error

        else:
            logger.error(f"Unexpected error during {operation}: {error}")
            raise AuthenticationProviderServiceUnavailableException("Unexpected authentication error") from error

    async def validate_token(
            self,
            token: str
    ) -> AuthenticationResponse:
        logger.debug("Validating token")
        self._token_validations += 1

        try:
            formatted_token = self._format_token(token)

            response = await self._http_client.get(
                url=self._authentication_validate_token_url,
                headers={
                    "Authorization": formatted_token
                }
            )

            user_data = response.json()
            user = self._parse_user_response(user_data)

            self._successful_operations += 1
            logger.info(f"Token validated successfully for user {user.id}")
            return user

        except ValueError as e:
            self._failed_operations += 1
            logger.error(f"Invalid response format: {e}")
            raise AuthenticationProviderInvalidTokenException("Invalid authentication response") from e

        except (HttpClientException,
                HttpClientTimeoutException,
                HttpClientConnectionException,
                HttpClientCircuitBreakerException) as e:
            self._failed_operations += 1
            self._handle_http_error(e, "token validation")

        except Exception as e:
            self._failed_operations += 1
            logger.error(f"Unexpected error validating token: {e}", exc_info=True)
            raise AuthenticationProviderServiceUnavailableException("Unexpected authentication error") from e

    async def verify_permissions(
            self,
            token: str,
            required_roles: List[str]
    ) -> AuthenticationResponse:
        logger.debug(f"Verifying permissions for roles: {required_roles}")
        self._permission_checks += 1

        try:
            formatted_token = self._format_token(token)

            response = await self._http_client.post(
                url=self._authentication_verify_permissions_url,
                headers={
                    "Authorization": formatted_token
                },
                json={
                    "roles": required_roles
                }
            )

            user_data = response.json()
            user = self._parse_user_response(user_data)

            if not user.has_any_role(required_roles):
                self._permission_denials += 1
                logger.warning(
                    f"User {user.id} lacks required roles. "
                    f"Has: {user.roles}, Required: {required_roles}"
                )
                raise AuthenticationProviderInsufficientPermissionsException(
                    message=f"Required roles: {', '.join(required_roles)}"
                )

            self._successful_operations += 1
            logger.info(f"User {user.id} has required permissions")
            return user

        except AuthenticationProviderInsufficientPermissionsException:
            self._failed_operations += 1
            raise

        except ValueError as e:
            self._failed_operations += 1
            logger.error(f"Invalid response format: {e}")
            raise AuthenticationProviderInvalidTokenException("Invalid authentication response") from e

        except (
                HttpClientException,
                HttpClientTimeoutException,
                HttpClientConnectionException,
                HttpClientCircuitBreakerException
        ) as e:
            self._failed_operations += 1
            self._handle_http_error(e, "permission verification")

        except Exception as e:
            self._failed_operations += 1
            logger.error(f"Unexpected error verifying permissions: {e}", exc_info=True)
            raise AuthenticationProviderServiceUnavailableException("Unexpected authentication error") from e

    async def get_user_by_token(
            self,
            token: str
    ) -> AuthenticationResponse:
        logger.debug("Getting user by token")
        self._user_retrievals += 1

        try:
            formatted_token = self._format_token(token)

            response = await self._http_client.get(
                url=self._authentication_get_user_by_token_url,
                headers={
                    "Authorization": formatted_token
                }
            )

            user_data = response.json()
            user = self._parse_user_response(user_data)

            self._successful_operations += 1
            logger.info(f"User retrieved successfully: {user.id}")
            return user

        except ValueError as e:
            self._failed_operations += 1
            logger.error(f"Invalid response format: {e}")
            raise AuthenticationProviderInvalidTokenException("Invalid authentication response") from e

        except (
                HttpClientException,
                HttpClientTimeoutException,
                HttpClientConnectionException,
                HttpClientCircuitBreakerException
        ) as e:
            self._failed_operations += 1
            self._handle_http_error(e, "user retrieval")

        except Exception as e:
            self._failed_operations += 1
            logger.error(f"Unexpected error getting user: {e}", exc_info=True)
            raise AuthenticationProviderServiceUnavailableException("Unexpected authentication error") from e

    def get_metrics(
            self
    ) -> Dict[str, int]:
        return {
            "token_validations": self._token_validations,
            "permission_checks": self._permission_checks,
            "user_retrievals": self._user_retrievals,
            "successful_operations": self._successful_operations,
            "failed_operations": self._failed_operations,
            "invalid_tokens": self._invalid_tokens,
            "permission_denials": self._permission_denials,
        }
