import json
import logging
from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.configuration.environment_variables import environment_variables

logger = logging.getLogger(__name__)


class _BodyTooLargeError(Exception):
    pass


class BodySizeLimitMiddleware:
    """Rejects request bodies above a configured byte limit with 413.

    Declared Content-Length values are checked up front; chunked bodies
    (no Content-Length) are counted as they stream in, so an oversized body is
    cut off without ever buffering it past the limit. Pydantic field limits
    bound individual values, but without this cap an arbitrarily large JSON
    body would still be read and parsed in full before validation runs.
    """

    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared_length = self._declared_content_length(scope)
        if declared_length is not None and declared_length > self.max_body_bytes:
            await self._send_too_large(scope, send)
            return

        received_bytes = 0
        response_started = False

        async def receive_wrapper() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_body_bytes:
                    raise _BodyTooLargeError()
            return message

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except _BodyTooLargeError:
            if response_started:
                raise
            await self._send_too_large(scope, send)

    async def _send_too_large(self, scope: Scope, send: Send) -> None:
        logger.warning(
            "Rejected a request body that exceeds the configured maximum size.",
            extra={
                "path": scope.get("path"),
                "max_body_bytes": self.max_body_bytes,
            },
        )
        body = json.dumps(
            {
                "error": "RequestBodyTooLarge",
                "message": "Request body exceeds the maximum allowed size.",
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    def _declared_content_length(scope: Scope) -> int | None:
        for key, value in scope.get("headers", []):
            if key.lower() == b"content-length":
                try:
                    return int(value)
                except ValueError:
                    return None
        return None


def add_body_size_limit_middleware(app: FastAPI) -> None:
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_body_bytes=environment_variables.max_request_body_bytes,
    )
