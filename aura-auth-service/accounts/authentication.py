import logging
import secrets

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from accounts.services.auth_service import get_user_info

logger = logging.getLogger(__name__)


class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return None

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return None

        user_info = get_user_info(token)
        if not user_info:
            logger.warning(
                "JWT authentication failed: invalid or expired token.",
                extra={"path": request.path},
            )
            raise AuthenticationFailed("Invalid or expired token.")

        logger.debug(
            "JWT authentication successful.",
            extra={"user_id": user_info["id"], "path": request.path},
        )
        return (user_info, token)

    def authenticate_header(self, request):
        return "Bearer"


class ServiceKeyAuthentication(BaseAuthentication):
    """Service-to-service authentication via X-Service-Api-Key header."""

    def authenticate(self, request):
        api_key = request.headers.get("X-Service-Api-Key")
        if not api_key:
            return None

        expected = getattr(settings, "SERVICE_API_KEY", "")
        if not expected:
            logger.error("SERVICE_API_KEY is not configured.")
            raise AuthenticationFailed("Service authentication not configured.")

        if not secrets.compare_digest(api_key.strip(), expected):
            logger.warning(
                "Service API key rejected.",
                extra={"path": request.path},
            )
            raise AuthenticationFailed("Invalid service API key.")

        logger.debug(
            "Service-to-service request authenticated.",
            extra={"path": request.path},
        )
        return ({"id": 0, "username": "service", "email": "service@internal", "roles": ["SERVICE"], "permissions": ["*"]}, api_key)

    def authenticate_header(self, request):
        return "X-Service-Api-Key"
