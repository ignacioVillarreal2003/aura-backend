import logging
import secrets
from typing import Optional

import httpx
from django.conf import settings

from core.authentication.authenticated_user import AuthenticatedUser
from core.authentication.exceptions import (
    AuthenticationProviderException,
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderServiceUnavailableException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderUserNotFoundException,
)

logger = logging.getLogger(__name__)

_HEADER_SERVICE_API_KEY = "X-Service-Api-Key"
_HEADER_USER_ID = "X-User-Id"
_HEADER_USER_EMAIL = "X-User-Email"
_HEADER_USER_ROLES = "X-User-Roles"
_HEADER_USER_PERMISSIONS = "X-User-Permissions"


class AuthenticationProvider:

    def evaluate_service_auth(self, request) -> Optional[AuthenticatedUser]:
        raw_key = request.headers.get(_HEADER_SERVICE_API_KEY)
        if raw_key is None:
            return None

        api_key = raw_key.strip()
        if not api_key:
            logger.warning(
                "Service API key header was present but empty.",
                extra={"path": request.path},
            )
            return None

        if not secrets.compare_digest(api_key, settings.SERVICE_API_KEY):
            logger.warning(
                "Service API key does not match the configured value.",
                extra={"path": request.path},
            )
            return None

        raw_user_id = request.headers.get(_HEADER_USER_ID, "").strip()
        if not raw_user_id:
            return None

        try:
            user_id = int(raw_user_id)
        except ValueError:
            return None

        email = request.headers.get(_HEADER_USER_EMAIL, "").strip()

        return AuthenticatedUser(
            id=user_id,
            email=email,
            roles=_parse_comma_list(request.headers.get(_HEADER_USER_ROLES)),
            permissions=_parse_comma_list(request.headers.get(_HEADER_USER_PERMISSIONS)),
        )

    async def validate_token(self, token: str) -> AuthenticatedUser:
        logger.debug("Validating bearer token with the authentication service.")
        bearer = token if token.lower().startswith("bearer ") else f"Bearer {token}"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    settings.AUTHENTICATION_SERVICE_URL,
                    headers={"Authorization": bearer},
                )

            if response.status_code == 401:
                raise AuthenticationProviderInvalidTokenException("Invalid or expired token")
            if response.status_code == 403:
                raise AuthenticationProviderUnauthorizedException("Access forbidden")
            if response.status_code == 404:
                raise AuthenticationProviderUserNotFoundException("User not found")
            if response.status_code >= 500:
                raise AuthenticationProviderServiceUnavailableException(
                    f"Authentication service error (HTTP {response.status_code})"
                )

            data = response.json()
            return AuthenticatedUser(
                id=data["id"],
                email=data.get("email", ""),
                roles=data.get("roles", []),
                permissions=data.get("permissions", []),
            )

        except httpx.TimeoutException as e:
            logger.error("Authentication service timed out.")
            raise AuthenticationProviderServiceUnavailableException(
                "Authentication service timeout"
            ) from e
        except httpx.ConnectError as e:
            logger.error("Could not connect to the authentication service.")
            raise AuthenticationProviderServiceUnavailableException(
                "Cannot connect to authentication service"
            ) from e
        except (
            AuthenticationProviderInvalidTokenException,
            AuthenticationProviderUnauthorizedException,
            AuthenticationProviderUserNotFoundException,
            AuthenticationProviderServiceUnavailableException,
        ):
            raise
        except Exception as e:
            logger.exception("Unexpected error while validating the bearer token.")
            raise AuthenticationProviderException(
                "Unexpected authentication error"
            ) from e


def _parse_comma_list(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


authentication_provider = AuthenticationProvider()
