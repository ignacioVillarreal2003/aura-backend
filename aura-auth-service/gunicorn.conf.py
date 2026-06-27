"""Configuracion de Gunicorn. Todo se puede ajustar por variables de entorno."""

import multiprocessing
import os

_cpu = multiprocessing.cpu_count()

bind = os.getenv('GUNICORN_BIND', '0.0.0.0:8000')
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gthread')

workers = int(os.getenv('GUNICORN_WORKERS', min((2 * _cpu) + 1, 6)))
threads = int(os.getenv('GUNICORN_THREADS', 4))

timeout = int(os.getenv('GUNICORN_TIMEOUT', 60))
graceful_timeout = int(os.getenv('GUNICORN_GRACEFUL_TIMEOUT', 30))
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', 5))

max_requests = int(os.getenv('GUNICORN_MAX_REQUESTS', 1000))
max_requests_jitter = int(os.getenv('GUNICORN_MAX_REQUESTS_JITTER', 100))

accesslog = os.getenv('GUNICORN_ACCESSLOG', '-')
errorlog = os.getenv('GUNICORN_ERRORLOG', '-')
loglevel = os.getenv('GUNICORN_LOGLEVEL', 'info')
