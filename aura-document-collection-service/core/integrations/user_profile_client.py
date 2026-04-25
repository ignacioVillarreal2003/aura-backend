import hashlib
import json
import logging
import random
import threading
import time
from dataclasses import dataclass
from typing import Iterable, Literal

import httpx
from django.conf import settings
from django.core.cache import cache

from core.authentication.authentication_provider import build_service_user_headers
from core.authentication.authenticated_user import AuthenticatedUser
from core.exceptions.base import ServiceUnavailableException

logger = logging.getLogger(__name__)

ProfileEnrichment = Literal["complete", "degraded", "failed"]


@dataclass(frozen=True)
class UserProfile:
    id: int
    email: str
    username: str


@dataclass(frozen=True)
class UserProfilesResult:
    profiles: dict[int, UserProfile]
    enrichment: ProfileEnrichment


class _CircuitBreaker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._open_until: float = 0.0

    def is_open(self) -> bool:
        with self._lock:
            return time.monotonic() < self._open_until

    def record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0

    def record_failure(self, fail_threshold: int, open_seconds: float) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= fail_threshold:
                self._open_until = time.monotonic() + open_seconds
                self._consecutive_failures = 0
                logger.warning(
                    "User profile client circuit opened.",
                    extra={"open_seconds": open_seconds, "fail_threshold": fail_threshold},
                )


_breaker = _CircuitBreaker()


def _cache_key(user_ids: tuple[int, ...]) -> str:
    digest = hashlib.sha256(json.dumps(list(user_ids)).encode()).hexdigest()[:32]
    return f"user_profiles:v1:{digest}"


def _empty_profiles(user_ids: tuple[int, ...]) -> dict[int, UserProfile]:
    return {uid: UserProfile(id=uid, email="", username="") for uid in user_ids}


def _parse_profile_rows(unique: tuple[int, ...], payload: object) -> dict[int, UserProfile]:
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


def _transient_http_status(status_code: int) -> bool:
    return status_code >= 500


class UserProfileClient:
    @staticmethod
    def fetch_by_ids(
        user_ids: Iterable[int],
        authenticated_user: AuthenticatedUser,
    ) -> UserProfilesResult:
        unique = tuple(sorted({int(uid) for uid in user_ids}))
        if not unique:
            return UserProfilesResult(profiles={}, enrichment="complete")

        strict = bool(getattr(settings, "USER_PROFILE_STRICT", False))
        url = (getattr(settings, "USER_PROFILE_SERVICE_URL", None) or "").strip()
        if not url:
            logger.warning("USER_PROFILE_SERVICE_URL is not configured.")
            if strict:
                raise ServiceUnavailableException(
                    detail="User profile service URL is not configured",
                    error_code="service_unavailable",
                )
            return UserProfilesResult(profiles=_empty_profiles(unique), enrichment="failed")

        ttl = int(getattr(settings, "USER_PROFILE_CACHE_TTL_SECONDS", 45))
        cache_key = _cache_key(unique)
        cached = cache.get(cache_key)
        if isinstance(cached, dict):
            try:
                profiles = {
                    int(k): UserProfile(
                        id=int(k),
                        email=str(v.get("email", "")),
                        username=str(v.get("username", "")),
                    )
                    for k, v in cached.items()
                }
                if set(profiles.keys()) == set(unique):
                    return UserProfilesResult(profiles=profiles, enrichment="complete")
            except (TypeError, ValueError, KeyError):
                pass

        fail_threshold = int(getattr(settings, "USER_PROFILE_BREAKER_FAIL_THRESHOLD", 5))
        open_seconds = int(getattr(settings, "USER_PROFILE_BREAKER_OPEN_SECONDS", 30))
        if _breaker.is_open():
            logger.warning("User profile circuit is open; skipping HTTP request.")
            if strict:
                raise ServiceUnavailableException(
                    detail="User profile service temporarily unavailable (circuit open)",
                    error_code="service_unavailable",
                )
            return UserProfilesResult(profiles=_empty_profiles(unique), enrichment="failed")

        timeout = float(getattr(settings, "USER_PROFILE_SERVICE_TIMEOUT", 5.0))
        max_retries = max(1, int(getattr(settings, "USER_PROFILE_MAX_RETRIES", 3)))
        headers = build_service_user_headers(authenticated_user)

        last_exc: BaseException | None = None
        response: httpx.Response | None = None

        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(
                        url,
                        json={"user_ids": list(unique)},
                        headers=headers,
                    )
            except httpx.RequestError as e:
                last_exc = e
                logger.warning(
                    "User profile service request failed.",
                    extra={"error": str(e), "attempt": attempt + 1},
                )
                if attempt < max_retries - 1:
                    time.sleep(min(2.0, 0.05 * (2**attempt) + random.uniform(0, 0.05)))
                    continue
                _breaker.record_failure(fail_threshold, open_seconds)
                if strict:
                    raise ServiceUnavailableException(
                        detail="User profile service request failed",
                        error_code="service_unavailable",
                    ) from e
                return UserProfilesResult(profiles=_empty_profiles(unique), enrichment="degraded")

            if response is None:
                break

            if _transient_http_status(response.status_code) and attempt < max_retries - 1:
                time.sleep(min(2.0, 0.05 * (2**attempt) + random.uniform(0, 0.05)))
                continue

            if response.status_code >= 500:
                logger.warning(
                    "User profile service returned a server error.",
                    extra={"status_code": response.status_code, "attempt": attempt + 1},
                )
                if attempt < max_retries - 1:
                    time.sleep(min(2.0, 0.05 * (2**attempt) + random.uniform(0, 0.05)))
                    continue
                _breaker.record_failure(fail_threshold, open_seconds)
                if strict:
                    raise ServiceUnavailableException(
                        detail=f"User profile service error (HTTP {response.status_code})",
                        error_code="service_unavailable",
                    )
                return UserProfilesResult(profiles=_empty_profiles(unique), enrichment="degraded")

            if response.status_code >= 400:
                logger.warning(
                    "User profile service returned a client error.",
                    extra={"status_code": response.status_code},
                )
                if strict:
                    raise ServiceUnavailableException(
                        detail=f"User profile service error (HTTP {response.status_code})",
                        error_code="service_unavailable",
                    )
                return UserProfilesResult(profiles=_empty_profiles(unique), enrichment="degraded")

            try:
                payload = response.json()
            except ValueError as e:
                logger.warning("User profile service returned non-JSON body.")
                _breaker.record_failure(fail_threshold, open_seconds)
                if strict:
                    raise ServiceUnavailableException(
                        detail="User profile service returned invalid JSON",
                        error_code="service_unavailable",
                    ) from e
                return UserProfilesResult(profiles=_empty_profiles(unique), enrichment="degraded")

            profiles = _parse_profile_rows(unique, payload)
            _breaker.record_success()
            cache.set(
                cache_key,
                {str(uid): {"email": p.email, "username": p.username} for uid, p in profiles.items()},
                ttl,
            )
            return UserProfilesResult(profiles=profiles, enrichment="complete")

        _breaker.record_failure(fail_threshold, open_seconds)
        if strict:
            raise ServiceUnavailableException(
                detail=str(last_exc) if last_exc else "User profile service unavailable",
                error_code="service_unavailable",
            ) from last_exc
        return UserProfilesResult(profiles=_empty_profiles(unique), enrichment="degraded")


user_profile_client = UserProfileClient()
