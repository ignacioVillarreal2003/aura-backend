from __future__ import annotations
import logging
from typing import Optional
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def lookup_recipient(user_id: int) -> Optional[dict]:
    base = settings.AUTHENTICATION_SERVICE_URL.rstrip("/")
    url = f"{base}/auth/users/{user_id}"
    try:
        response = requests.get(
            url,
            headers={"X-Service-Api-Key": str(settings.SERVICE_API_KEY)},
            timeout=5,
        )
    except requests.RequestException as exc:
        logger.warning("Recipient lookup network error for user %s: %s", user_id, exc)
        raise
    if response.status_code == 404:
        return None
    if response.status_code >= 500:
        logger.warning(
            "Recipient lookup returned %s for user %s — retryable.",
            response.status_code,
            user_id,
        )
        response.raise_for_status()
    if not response.ok:
        logger.warning(
            "Recipient lookup returned %s for user %s.",
            response.status_code,
            user_id,
        )
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    return {
        "email": data.get("email"),
        "username": data.get("username"),
    }
