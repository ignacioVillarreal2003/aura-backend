"""DRF authentication backends for the auth API.

Wired as ``DEFAULT_AUTHENTICATION_CLASSES`` (see settings) so views use the
standard DRF auth/permission pipeline instead of parsing the Authorization
header by hand. ``JWTAuthentication`` resolves a real ``User``;
``ServiceKeyAuthentication`` resolves a non-user ``ServiceAccount`` principal
for trusted service-to-service calls.
"""

import logging
import secrets

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.services.auth_service import authenticate_access_token

logger = logging.getLogger(__name__)


class ServiceAccount:
    """Minimal authenticated principal for service-to-service requests.

    Not a DB-backed user — it only needs to satisfy DRF's ``IsAuthenticated``
    (``is_authenticated`` truthy). Views that require a real end user must
    authenticate with ``JWTAuthentication`` instead.
    """

    is_authenticated = True
    is_active = True
    is_service = True
    is_superuser = False
    id = 0
    pk = 0
    username = "service"

    def __str__(self):
        return "service"


class JWTAuthentication(BaseAuthentication):
    """Bearer access-token authentication. Returns ``None`` when no Bearer
    header is present (so other backends can try); raises only when a Bearer
    token is present but invalid/expired/revoked."""

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return None

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return None

        user = authenticate_access_token(token)
        if not user:
            logger.warning(
                "JWT authentication failed: invalid or expired token.",
                extra={"path": request.path},
            )
            raise AuthenticationFailed("Invalid or expired token.")

        return (user, token)

    def authenticate_header(self, request):
        return "Bearer"


class ServiceKeyAuthentication(BaseAuthentication):
    """Service-to-service authentication via the ``X-Service-Api-Key`` header.

    Returns ``None`` when the header is absent (so Bearer auth can run);
    raises when the header is present but the key is wrong."""

    def authenticate(self, request):
        api_key = request.headers.get("X-Service-Api-Key")
        if not api_key:
            return None

        expected = getattr(settings, "SERVICE_API_KEY", "")
        if not expected:
            logger.error("SERVICE_API_KEY is not configured.")
            raise AuthenticationFailed("Service authentication not configured.")

        if not secrets.compare_digest(api_key.strip(), str(expected)):
            logger.warning("Service API key rejected.", extra={"path": request.path})
            raise AuthenticationFailed("Invalid service API key.")

        return (ServiceAccount(), api_key)

    def authenticate_header(self, request):
        return "X-Service-Api-Key"
