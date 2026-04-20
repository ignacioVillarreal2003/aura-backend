import logging
from dataclasses import dataclass
from typing import Iterable
import httpx
from django.conf import settings

from core.authentication.authenticated_user import AuthenticatedUser
from core.authentication.authentication_provider import build_service_user_headers

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UserProfile:
    id: int
    email: str
    username: str


class UserProfileClient:
    @staticmethod
    def fetch_by_ids(
        user_ids: Iterable[int],
        authenticated_user: AuthenticatedUser,
    ) -> dict[int, UserProfile]:
        unique = sorted({int(uid) for uid in user_ids})
        if not unique:
            return {}
        url = (getattr(settings, "USER_PROFILE_SERVICE_URL", None)).strip()

        timeout = float(getattr(settings, "USER_PROFILE_SERVICE_TIMEOUT", 5.0))
        headers = build_service_user_headers(authenticated_user)
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    url,
                    json={"user_ids": unique},
                    headers=headers,
                )
        except (httpx.HTTPError, ValueError, TypeError) as e:
            logger.warning(
                "User profile service request failed; using placeholder profiles.",
                extra={"error": str(e)},
            )
            return {uid: UserProfile(id=uid, email="", username="") for uid in unique}

        if response.status_code >= 400:
            logger.warning(
                "User profile service returned an error status.",
                extra={"status_code": response.status_code},
            )
            return {uid: UserProfile(id=uid, email="", username="") for uid in unique}

        try:
            payload = response.json()
        except ValueError:
            logger.warning("User profile service returned non-JSON body.")
            return {uid: UserProfile(id=uid, email="", username="") for uid in unique}

        rows: list[dict] = []
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            for key in ("users", "data", "results"):
                if isinstance(payload.get(key), list):
                    rows = payload[key]
                    break

        by_id: dict[int, UserProfile] = {uid: UserProfile(id=uid, email="", username="") for uid in unique}
        for item in rows:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id", item.get("user_id"))
            try:
                uid = int(raw_id)
            except (TypeError, ValueError):
                continue
            if uid not in by_id:
                continue
            email = str(item.get("email", "") or "")
            username = str(item.get("username", item.get("user_name", "")) or "")
            by_id[uid] = UserProfile(id=uid, email=email, username=username)
        return by_id


user_profile_client = UserProfileClient()
