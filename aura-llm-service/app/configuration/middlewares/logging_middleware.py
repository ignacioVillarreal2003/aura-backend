import logging
import time
import uuid
from typing import Optional
from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.infrastructure.http.request_id_context import set_request_id

logger = logging.getLogger(__name__)

_X_REQUEST_ID = "X-Request-ID"
_X_REQUEST_ID_BYTES = b"x-request-id"
_SKIP_PATHS = frozenset({"/metrics", "/api/v1/health", "/api/v1/ready"})


class LoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope.get("path") in _SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        request_id = self._resolve_request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        set_request_id(request_id)

        started = time.perf_counter()
        status_holder = {"code": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
                headers = [
                    (k, v)
                    for (k, v) in message.get("headers", [])
                    if k.lower() != _X_REQUEST_ID_BYTES
                ]
                headers.append((_X_REQUEST_ID_BYTES, request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            state = scope.get("state") or {}
            auth_user = state.get("authenticated_user")
            user_id: Optional[int] = (
                auth_user.id if auth_user is not None and hasattr(auth_user, "id") else None
            )
            method = scope.get("method")
            path = scope.get("path")
            logger.info(
                "HTTP %s %s %s in %sms",
                method,
                path,
                status_holder["code"],
                duration_ms,
                extra={
                    "request_id": request_id,
                    "http_method": method,
                    "path": path,
                    "status_code": status_holder["code"],
                    "duration_ms": duration_ms,
                    "user_id": user_id,
                },
            )

    @staticmethod
    def _resolve_request_id(scope: Scope) -> str:
        for key, value in scope.get("headers", []):
            if key.lower() == _X_REQUEST_ID_BYTES:
                candidate = value.decode("latin-1").strip()
                if candidate:
                    return candidate
                break
        return str(uuid.uuid4())


def add_logging_middleware(app: FastAPI) -> None:
    app.add_middleware(LoggingMiddleware)
