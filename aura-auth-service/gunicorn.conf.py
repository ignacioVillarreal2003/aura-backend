"""Gunicorn configuration for aura-auth-service.

Everything is overridable by environment variable so the deploy can be tuned
without rebuilding the image. Defaults are sane for a small production box.

Connection-budget note: with ``CONN_MAX_AGE`` set and two databases, this
service can hold up to ``workers x threads x 2`` persistent PostgreSQL
connections. The worker default is capped (see ``workers`` below) so a
many-core host does not silently exhaust Postgres ``max_connections`` across
the whole fleet. Raise ``GUNICORN_WORKERS`` only after confirming the database
(or PgBouncer) can absorb the extra connections.
"""

import multiprocessing
import os

_cpu = multiprocessing.cpu_count()

bind = os.getenv('GUNICORN_BIND', '0.0.0.0:8000')
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gthread')

# (2 x CPU) + 1 is the usual starting point, capped to keep the Postgres
# connection budget bounded on large hosts.
workers = int(os.getenv('GUNICORN_WORKERS', min((2 * _cpu) + 1, 6)))
threads = int(os.getenv('GUNICORN_THREADS', 4))

timeout = int(os.getenv('GUNICORN_TIMEOUT', 60))
graceful_timeout = int(os.getenv('GUNICORN_GRACEFUL_TIMEOUT', 30))
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', 5))

# Recycle workers periodically to bound memory growth from any slow leak. The
# jitter avoids all workers restarting at once.
max_requests = int(os.getenv('GUNICORN_MAX_REQUESTS', 1000))
max_requests_jitter = int(os.getenv('GUNICORN_MAX_REQUESTS_JITTER', 100))

accesslog = os.getenv('GUNICORN_ACCESSLOG', '-')
errorlog = os.getenv('GUNICORN_ERRORLOG', '-')
loglevel = os.getenv('GUNICORN_LOGLEVEL', 'info')
