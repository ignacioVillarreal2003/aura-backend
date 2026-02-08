import logging
from typing import List
from aiohttp.web_exceptions import HTTPClientError

from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
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
    HttpClientConnectionException
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

        logger.info("AuthenticationProvider initialized")

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

    async def validate_token(
            self,
            token: str
    ) -> AuthenticationResponse:
        logger.debug("Validating token")

        try:
            formatted_token = self._format_token(token)

            response = await self._http_client.get(
                url=self._authentication_validate_token_url,
                headers={"Authorization": formatted_token}
            )

            user_data = response.json()
            user = self._parse_user_response(user_data)

            logger.info(f"Token validated successfully for user {user.id}")
            return user

        except HttpClientTimeoutException as e:
            logger.error(f"Timeout validating token: {e}")
            raise AuthenticationProviderServiceUnavailableException(
                "Authentication service timeout"
            ) from e

        except HttpClientConnectionException as e:
            logger.error(f"Connection error validating token: {e}")
            raise AuthenticationProviderServiceUnavailableException(
                "Cannot connect to authentication service"
            ) from e

        except HttpClientCircuitBreakerException as e:
            logger.error(f"Circuit breaker open: {e}")
            raise AuthenticationProviderServiceUnavailableException(
                "Authentication service temporarily unavailable"
            ) from e

        except HTTPClientError as e:
            error_message = str(e)

            if "401" in error_message or "Unauthorized" in error_message:
                logger.warning("Invalid token provided")
                raise AuthenticationProviderInvalidTokenException("Invalid or expired token") from e

            elif "403" in error_message or "Forbidden" in error_message:
                logger.warning("Access forbidden")
                raise AuthenticationProviderUnauthorizedException("Access forbidden") from e

            elif "404" in error_message or "Not Found" in error_message:
                logger.warning("User not found")
                raise AuthenticationProviderUserNotFoundException("User not found") from e

            else:
                logger.error(f"HTTP error validating token: {e}")
                raise AuthenticationProviderServiceUnavailableException(
                    f"Authentication service error: {error_message}"
                ) from e

        except ValueError as e:
            logger.error(f"Invalid response format: {e}")
            raise AuthenticationProviderInvalidTokenException("Invalid authentication response") from e

        except Exception as e:
            logger.error(f"Unexpected error validating token: {e}", exc_info=True)
            raise AuthenticationProviderServiceUnavailableException(
                "Unexpected authentication error"
            ) from e

    async def verify_permissions(
            self,
            token: str,
            required_roles: List[str]
    ) -> AuthenticationResponse:
        logger.debug(f"Verifying permissions for roles: {required_roles}")

        try:
            formatted_token = self._format_token(token)

            response = await self._http_client.post(
                url=self._authentication_verify_permissions_url,
                headers={"Authorization": formatted_token},
                json={"roles": required_roles}
            )

            user_data = response.json()
            user = self._parse_user_response(user_data)

            if not user.has_any_role(required_roles):
                logger.warning(
                    f"User {user.id} lacks required roles. "
                    f"Has: {user.roles}, Required: {required_roles}"
                )
                raise AuthenticationProviderInsufficientPermissionsException(
                    message=f"Required roles: {', '.join(required_roles)}"
                )

            logger.info(f"User {user.id} has required permissions")
            return user

        except AuthenticationProviderInsufficientPermissionsException:
            raise

        except HttpClientTimeoutException as e:
            logger.error(f"Timeout verifying permissions: {e}")
            raise AuthenticationProviderServiceUnavailableException(
                "Authentication service timeout"
            ) from e

        except HttpClientConnectionException as e:
            logger.error(f"Connection error verifying permissions: {e}")
            raise AuthenticationProviderServiceUnavailableException(
                "Cannot connect to authentication service"
            ) from e

        except HttpClientCircuitBreakerException as e:
            logger.error(f"Circuit breaker open: {e}")
            raise AuthenticationProviderServiceUnavailableException(
                "Authentication service temporarily unavailable"
            ) from e

        except HTTPClientError as e:
            error_message = str(e)

            if "401" in error_message or "Unauthorized" in error_message:
                logger.warning("Invalid token provided")
                raise AuthenticationProviderInvalidTokenException("Invalid or expired token") from e

            elif "403" in error_message or "Forbidden" in error_message:
                logger.warning("Access forbidden or insufficient permissions")
                raise AuthenticationProviderInsufficientPermissionsException(
                    message=f"Required roles: {', '.join(required_roles)}"
                ) from e

            elif "404" in error_message or "Not Found" in error_message:
                logger.warning("User not found")
                raise AuthenticationProviderUserNotFoundException("User not found") from e

            else:
                logger.error(f"HTTP error verifying permissions: {e}")
                raise AuthenticationProviderServiceUnavailableException(
                    f"Authentication service error: {error_message}"
                ) from e

        except ValueError as e:
            logger.error(f"Invalid response format: {e}")
            raise AuthenticationProviderInvalidTokenException("Invalid authentication response") from e

        except Exception as e:
            logger.error(f"Unexpected error verifying permissions: {e}", exc_info=True)
            raise AuthenticationProviderServiceUnavailableException(
                "Unexpected authentication error"
            ) from e

    async def get_user_by_token(
            self,
            token: str
    ) -> AuthenticationResponse:
        logger.debug("Getting user by token")

        try:
            formatted_token = self._format_token(token)

            response = await self._http_client.get(
                url=self._authentication_get_user_by_token_url,
                headers={"Authorization": formatted_token}
            )

            user_data = response.json()
            user = self._parse_user_response(user_data)

            logger.info(f"User retrieved successfully: {user.id}")
            return user

        except HttpClientTimeoutException as e:
            logger.error(f"Timeout getting user: {e}")
            raise AuthenticationProviderServiceUnavailableException(
                "Authentication service timeout"
            ) from e

        except HttpClientConnectionException as e:
            logger.error(f"Connection error getting user: {e}")
            raise AuthenticationProviderServiceUnavailableException(
                "Cannot connect to authentication service"
            ) from e

        except HttpClientCircuitBreakerException as e:
            logger.error(f"Circuit breaker open: {e}")
            raise AuthenticationProviderServiceUnavailableException(
                "Authentication service temporarily unavailable"
            ) from e

        except HTTPClientError as e:
            error_message = str(e)

            if "401" in error_message or "Unauthorized" in error_message:
                logger.warning("Invalid token provided")
                raise AuthenticationProviderInvalidTokenException("Invalid or expired token") from e

            elif "403" in error_message or "Forbidden" in error_message:
                logger.warning("Access forbidden")
                raise AuthenticationProviderUnauthorizedException("Access forbidden") from e

            elif "404" in error_message or "Not Found" in error_message:
                logger.warning("User not found")
                raise AuthenticationProviderUserNotFoundException("User not found") from e

            else:
                logger.error(f"HTTP error getting user: {e}")
                raise AuthenticationProviderServiceUnavailableException(
                    f"Authentication service error: {error_message}"
                ) from e

        except ValueError as e:
            logger.error(f"Invalid response format: {e}")
            raise AuthenticationProviderInvalidTokenException("Invalid authentication response") from e

        except Exception as e:
            logger.error(f"Unexpected error getting user: {e}", exc_info=True)
            raise AuthenticationProviderServiceUnavailableException(
                "Unexpected authentication error"
            ) from e
