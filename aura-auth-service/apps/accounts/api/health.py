"""Liveness and readiness probes.

Plain unauthenticated Django views (no DRF, no DB writes), kept cheap so an
orchestrator can poll them frequently:

* ``/health/live``  — process is up (always 200). Use for liveness restarts.
* ``/health/ready`` — process can serve traffic: ``auth_db`` (the hard
  dependency for login/validate) must be reachable. ``aura_db`` is probed and
  reported but does NOT gate readiness, since auth core works without it.
"""

import logging

from django.db import connections
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def _db_ok(alias: str) -> bool:
    try:
        with connections[alias].cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return True
    except Exception:
        logger.warning('health: database %s is not reachable', alias, exc_info=True)
        return False


def liveness(request):
    return JsonResponse({'status': 'alive'})


def readiness(request):
    auth_db_ok = _db_ok('default')
    aura_db_ok = _db_ok('aura_db')  # reported only — not a readiness gate
    ready = auth_db_ok
    return JsonResponse(
        {
            'status': 'ready' if ready else 'not_ready',
            'checks': {
                'auth_db': 'ok' if auth_db_ok else 'error',
                'aura_db': 'ok' if aura_db_ok else 'error',
            },
        },
        status=200 if ready else 503,
    )
