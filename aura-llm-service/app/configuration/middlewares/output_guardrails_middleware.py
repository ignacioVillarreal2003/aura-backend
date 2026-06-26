import json
import logging
from typing import Optional
from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.configuration.metrics import record_guardrails_block

logger = logging.getLogger(__name__)

_EXCLUDED_PATH_PREFIXES = (
    "/api/v1/health",
    "/api/v1/ready",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/metrics",
    "/api/v1/document-classify",
    "/api/v1/fragment-contextualize",
    "/api/v1/graph-extraction",
    "/api/v1/graph-query-translation",
)

_TEXT_FIELDS = ("answer", "content", "response", "message", "text", "summary")

_MAX_BUFFER_BYTES = 1_048_576
_MAX_CHECK_CHARS = 16_000


def _collect_texts(payload: object, out: list[str], budget: int) -> int:
    if budget <= 0:
        return budget
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, str):
                if key in _TEXT_FIELDS and value.strip():
                    out.append(value)
                    budget -= len(value)
            else:
                budget = _collect_texts(value, out, budget)
            if budget <= 0:
                break
    elif isinstance(payload, list):
        for item in payload:
            budget = _collect_texts(item, out, budget)
            if budget <= 0:
                break
    return budget


class OutputGuardrailsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self._is_candidate(scope):
            await self.app(scope, receive, send)
            return

        guardrails = getattr(scope["app"].state, "nemo_guardrails", None)
        settings = getattr(guardrails, "settings", None)
        if guardrails is None or settings is None or not getattr(settings, "check_output", False) \
                or not guardrails.is_active:
            await self.app(scope, receive, send)
            return

        await self._screen(scope, receive, send, guardrails, settings)

    @staticmethod
    def _is_candidate(scope: Scope) -> bool:
        if scope["type"] != "http" or scope.get("method") != "POST":
            return False
        path = scope.get("path", "")
        if not path.startswith("/api/v1") or path.startswith(_EXCLUDED_PATH_PREFIXES):
            return False
        return not path.endswith("/stream")

    async def _screen(self, scope, receive, send, guardrails, settings) -> None:
        start_message: Optional[Message] = None
        body_chunks: list[bytes] = []
        passthrough = False
        buffered = 0

        async def buffering_send(message: Message) -> None:
            nonlocal start_message, passthrough, buffered

            if passthrough:
                await send(message)
                return

            if message["type"] == "http.response.start":
                content_type = b""
                for key, value in message.get("headers", []):
                    if key.lower() == b"content-type":
                        content_type = value
                        break
                if message["status"] != 200 or not content_type.lower().startswith(b"application/json"):
                    passthrough = True
                    await send(message)
                    return
                start_message = message
                return

            if message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))
                buffered += len(message.get("body", b""))
                more = message.get("more_body", False)
                if buffered > _MAX_BUFFER_BYTES:
                    passthrough = True
                    if start_message is not None:
                        await send(start_message)
                        start_message = None
                    for chunk in body_chunks:
                        await send({"type": "http.response.body", "body": chunk, "more_body": True})
                    body_chunks.clear()
                    await send({"type": "http.response.body", "body": b"", "more_body": more})
                    return
                if more:
                    return
                await self._finalize(scope, send, guardrails, settings, start_message, body_chunks)
                return

            await send(message)

        await self.app(scope, receive, buffering_send)

    async def _finalize(self, scope, send, guardrails, settings, start_message, body_chunks) -> None:
        full_body = b"".join(body_chunks)

        verdict_allowed = True
        try:
            payload = json.loads(full_body) if full_body else None
            texts: list[str] = []
            if payload is not None:
                _collect_texts(payload, texts, _MAX_CHECK_CHARS)
            if texts:
                verdict = await guardrails.check_output("\n\n".join(texts))
                verdict_allowed = verdict.allowed
        except (UnicodeDecodeError, json.JSONDecodeError):
            verdict_allowed = True
        except Exception:
            logger.exception("Output guardrail screening failed; forwarding original response.")
            verdict_allowed = True

        if verdict_allowed:
            if start_message is not None:
                await send(start_message)
            await send({"type": "http.response.body", "body": full_body, "more_body": False})
            return

        await self._send_blocked(scope, send, settings.blocked_output_message)

    @staticmethod
    async def _send_blocked(scope: Scope, send: Send, message: str) -> None:
        record_guardrails_block("output")
        request_id = (scope.get("state") or {}).get("request_id")
        logger.warning(
            "Response blocked by the guardrails output filter.",
            extra={"path": scope.get("path"), "request_id": request_id},
        )
        content: dict = {"error": "output_blocked_by_guardrails", "message": message}
        if request_id:
            content["request_id"] = request_id
        body = json.dumps(content, ensure_ascii=False).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("latin-1")),
        ]
        if request_id:
            headers.append((b"x-request-id", request_id.encode("latin-1")))
        await send({"type": "http.response.start", "status": 400, "headers": headers})
        await send({"type": "http.response.body", "body": body})


def add_output_guardrails_middleware(app: FastAPI) -> None:
    app.add_middleware(OutputGuardrailsMiddleware)
