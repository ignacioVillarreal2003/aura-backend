import logging
import time

logger = logging.getLogger(__name__)


def _get_client_ip(request) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


_SKIP_PATHS = frozenset({"/metrics", "/api/v1/health"})


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in _SKIP_PATHS:
            return self.get_response(request)

        start = time.monotonic()
        status_code = 500
        try:
            response = self.get_response(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            user = getattr(request, "authenticated_user", None)
            logger.info(
                "%s %s %s %.1fms",
                request.method,
                request.path,
                status_code,
                duration_ms,
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 1),
                    "user_id": user.id if user else None,
                    "client_ip": _get_client_ip(request),
                },
            )
