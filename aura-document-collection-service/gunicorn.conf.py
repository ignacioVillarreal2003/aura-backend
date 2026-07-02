import os


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")

workers = _int_env("GUNICORN_WORKERS", 3)
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gthread")
threads = _int_env("GUNICORN_THREADS", 4)

timeout = _int_env("GUNICORN_TIMEOUT", 30)
graceful_timeout = _int_env("GUNICORN_GRACEFUL_TIMEOUT", 30)
keepalive = _int_env("GUNICORN_KEEPALIVE", 5)

max_requests = _int_env("GUNICORN_MAX_REQUESTS", 1000)
max_requests_jitter = _int_env("GUNICORN_MAX_REQUESTS_JITTER", 100)

errorlog = "-"
accesslog = os.environ.get("GUNICORN_ACCESS_LOG") or None
