import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import Response

logger = logging.getLogger(__name__)

_X_REQUEST_ID = "X-Request-ID"
_SKIP_PATHS = frozenset({"/metrics", "/api/v1/health", "/api/v1/ready"})


def add_logging_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        incoming = request.headers.get(_X_REQUEST_ID)
        request_id = incoming.strip() if incoming and incoming.strip() else str(uuid.uuid4())
        request.state.request_id = request_id

        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)

        response.headers[_X_REQUEST_ID] = request_id

        auth_user = getattr(request.state, "authenticated_user", None)
        user_id: Optional[int] = (
            auth_user.id if auth_user is not None and hasattr(auth_user, "id") else None
        )

        logger.info(
            "HTTP %s %s %s in %sms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "request_id": request_id,
                "http_method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user_id": user_id,
            },
        )
        return response
