"""Probes de liveness y readiness.

/health/live indica que el proceso esta vivo; /health/ready exige que auth_db
este accesible (aura_db se reporta pero no condiciona el readiness).
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
    aura_db_ok = _db_ok('aura_db')  # se reporta pero no condiciona el readiness
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
