"""Auth service client for JWT introspection."""

import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def validate_token(token: str) -> dict | None:
    """
    Call aura-auth-service GET /auth/validate to validate a JWT.

    Returns a dict with keys: id, email, username, roles, permissions
    or None if the token is invalid or the auth service is unreachable.
    """
    try:
        response = requests.get(
            f"{settings.AUTH_SERVICE_URL}/auth/validate",
            headers={'Authorization': f'Bearer {token}'},
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            # Normalize: notification views expect 'user_id' key
            data.setdefault('user_id', data.get('id'))
            return data
        return None
    except requests.RequestException as exc:
        logger.error("Auth service validate failed: %s", exc)
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
    return validate_token(token)
