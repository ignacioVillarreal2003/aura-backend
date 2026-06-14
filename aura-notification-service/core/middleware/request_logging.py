import logging
import time

logger = logging.getLogger(__name__)


_SKIP_PATHS = frozenset({"/metrics", "/api/v1/health"})


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in _SKIP_PATHS:
            return self.get_response(request)

        start = time.monotonic()

        response = self.get_response(request)

        duration_ms = (time.monotonic() - start) * 1000
        user = getattr(request, "authenticated_user", None)
        logger.info(
            "%s %s %s %.1fms",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            extra={
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 1),
                "user_id": getattr(user, "id", None),
            },
        )
        return response
