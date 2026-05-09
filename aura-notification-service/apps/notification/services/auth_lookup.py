"""Best-effort recipient lookup against the central authentication service.

Used by the email task when the producer of an event did not embed
`recipient_email` in the context. The auth-service is expected to expose
a `/auth/users/{id}` endpoint returning at least `email` and optionally
`username`. If the call fails or the endpoint is missing, the email is
considered unsendable and the dispatch is marked failed (with the
in-app row already saved, so nothing is silently lost).
"""

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
            headers={
                "X-Service-Api-Key": str(settings.SERVICE_API_KEY),
                "X-Internal-Token": str(settings.NOTIFICATION_INTERNAL_API_TOKEN),
            },
            timeout=5,
        )
    except requests.RequestException as exc:
        logger.warning("Recipient lookup failed for user %s: %s", user_id, exc)
        return None
    if response.status_code != 200:
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
