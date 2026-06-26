"""Resilient, Redis-backed DRF throttles.

DRF's stock throttles use the ``default`` cache (LocMem), which is per-process:
with multiple gunicorn workers the configured rate is effectively multiplied by
the worker count and reset on every restart. These throttles use the dedicated
Redis ``throttle`` cache instead, so the limit is shared and accurate across
workers.

They *fail open*: if Redis is unavailable the throttle allows the request rather
than 500-ing. This preserves the original design intent that a Redis outage must
never break auth — the per-account DB lockout (see ``auth_service``) remains the
hard brute-force backstop and does not depend on Redis.
"""

import logging

from django.core.cache import caches
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle

logger = logging.getLogger(__name__)

_throttle_cache = caches['throttle']


class _ResilientMixin:
    """Route throttle state to the Redis ``throttle`` cache, failing open."""

    cache = _throttle_cache

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except Exception:
            # Redis unreachable: degrade gracefully instead of erroring the
            # request. The DB account-lockout still bounds brute force.
            logger.warning('throttle cache unavailable; failing open', exc_info=True)
            return True


class LoginRateThrottle(_ResilientMixin, AnonRateThrottle):
    scope = 'login'


class ScopedRedisThrottle(_ResilientMixin, ScopedRateThrottle):
    pass
