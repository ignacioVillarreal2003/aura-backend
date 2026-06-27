"""Throttles de DRF sobre Redis, compartidos entre workers.

Si Redis no responde dejan pasar la peticion en vez de fallar; el bloqueo de
cuenta en la base de datos sigue frenando los ataques de fuerza bruta.
"""

import logging

from django.core.cache import caches
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle

logger = logging.getLogger(__name__)

_throttle_cache = caches['throttle']


class _ResilientMixin:
    """Usa la cache Redis de throttle y deja pasar si falla."""

    cache = _throttle_cache

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except Exception:
            logger.warning('throttle cache unavailable; failing open', exc_info=True)
            return True


class LoginRateThrottle(_ResilientMixin, AnonRateThrottle):
    scope = 'login'


class ScopedRedisThrottle(_ResilientMixin, ScopedRateThrottle):
    pass
