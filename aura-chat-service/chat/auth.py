"""Remote authentication backend for Django REST Framework.

Delegates token validation to the external auth service (AUTH_SERVICE_URL).

Behaviour
---------
Production (DEBUG=False):
  * Missing or malformed Authorization header → 401 Unauthorized.
  * Auth service returns non-200 or is unreachable → 401 Unauthorized.

Development (DEBUG=True):
  * Missing token or auth service failure → falls back to user_id=1 so you
    can test without a running auth service.

The raw Bearer token is attached to ``request.bearer_token`` so downstream
code can forward it to the LLM service without re-parsing the header.
"""

import logging

import httpx
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)

_AUTH_TIMEOUT = 5.0  # seconds


class MockUser:
    """Minimal user object; the service has no Django User model."""

    def __init__(
        self,
        user_id: int,
        email: str = "",
        username: str = "",
        roles: list | None = None,
        permissions: list | None = None,
    ):
        self.id = user_id
        self.email = email
        self.username = username
        self.roles = roles or []
        self.permissions = permissions or []
        self.is_authenticated = True

    def __str__(self) -> str:
        return f"User({self.id})"


def _user_from_response(data: dict) -> "MockUser":
    return MockUser(
        user_id=data["id"],
        email=data.get("email", ""),
        username=data.get("username", ""),
        roles=data.get("roles", []),
        permissions=data.get("permissions", []),
    )


def _dev_fallback(request, token: str | None = None) -> tuple:
    """Return a dev-only anonymous user when the auth service is unavailable."""
    request.bearer_token = token or "user_token_123"
    return (MockUser(1), None)


class RemoteAuthAuthentication(BaseAuthentication):
    """Validates tokens by calling the external auth service synchronously.

    Used by all DRF-based views (ChatListView, ChatDetailView, etc.).
    """

    def authenticate(self, request):
        auth_header: str = request.META.get("HTTP_AUTHORIZATION", "")

        if not auth_header.startswith("Bearer "):
            if settings.DEBUG:
                return _dev_fallback(request)
            return None

        token = auth_header[7:]
        user = self._call_auth_service(auth_header)

        if user is None:
            if settings.DEBUG:
                logger.debug("Auth service failed — falling back to user_id=1")
                return _dev_fallback(request, token)
            raise AuthenticationFailed("Invalid or expired token.")

        request.bearer_token = token
        return (user, token)

    @staticmethod
    def _call_auth_service(auth_header: str) -> "MockUser | None":
        url = f"{settings.AUTH_SERVICE_URL}/auth/validate"
        try:
            with httpx.Client(timeout=_AUTH_TIMEOUT) as client:
                resp = client.get(url, headers={"Authorization": auth_header})
            if resp.status_code == 200:
                return _user_from_response(resp.json())
            logger.warning("Auth service rejected token: HTTP %d", resp.status_code)
            return None
        except httpx.RequestError as exc:
            logger.error("Auth service unreachable: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Async variant — used by SSEChatStreamView
    # ------------------------------------------------------------------

    async def authenticate_async(self, request) -> tuple | None:
        """Same logic as authenticate() but uses httpx.AsyncClient."""
        auth_header: str = request.META.get("HTTP_AUTHORIZATION", "")

        if not auth_header.startswith("Bearer "):
            if settings.DEBUG:
                return _dev_fallback(request)
            return None

        token = auth_header[7:]
        user = await self._call_auth_service_async(auth_header)

        if user is None:
            if settings.DEBUG:
                logger.debug("Auth service failed (async) — falling back to user_id=1")
                return _dev_fallback(request, token)
            return None

        request.bearer_token = token
        return (user, token)

    @staticmethod
    async def _call_auth_service_async(auth_header: str) -> "MockUser | None":
        url = f"{settings.AUTH_SERVICE_URL}/auth/validate"
        try:
            async with httpx.AsyncClient(timeout=_AUTH_TIMEOUT) as client:
                resp = await client.get(url, headers={"Authorization": auth_header})
            if resp.status_code == 200:
                return _user_from_response(resp.json())
            logger.warning("Auth service rejected token (async): HTTP %d", resp.status_code)
            return None
        except httpx.RequestError as exc:
            logger.error("Auth service unreachable (async): %s", exc)
            return None


# Keep the old name as an alias so that settings.py and any external code
# referencing JWTAuthentication keeps working without changes.
JWTAuthentication = RemoteAuthAuthentication
