"""Auth service client for JWT introspection."""

import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def introspect_token(token: str) -> dict | None:
    """
    Call aura-auth-service /auth/introspect to validate a JWT.

    Returns a dict with keys: user_id, roles, permissions, is_super_admin
    or None if the token is invalid or the auth service is unreachable.
    """
    try:
        response = requests.post(
            f"{settings.AUTH_SERVICE_URL}/auth/introspect",
            json={'token': token},
            timeout=5,
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.RequestException as exc:
        logger.error("Auth service introspect failed: %s", exc)
        return None


def get_user_from_request(request) -> dict | None:
    """
    Extract and validate the JWT from the Authorization header.

    Returns the auth payload dict or None if missing / invalid.
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ', 1)[1]
    return introspect_token(token)
