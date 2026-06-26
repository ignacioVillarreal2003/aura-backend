import json
import logging
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
)

_USER_TEXT_FIELDS = ("instruction", "question")


def extract_user_texts(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return []

    texts: list[str] = []

    messages = payload.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "human":
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    texts.append(content)
                break

    for field in _USER_TEXT_FIELDS:
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            texts.append(value)

    return texts


class GuardrailsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/api/v1") or path.startswith(_EXCLUDED_PATH_PREFIXES):
            await self.app(scope, receive, send)
            return

        guardrails = getattr(scope["app"].state, "nemo_guardrails", None)
        if guardrails is None or not guardrails.is_active:
            await self.app(scope, receive, send)
            return

        body = await self._read_body(receive)

        body_replayed = False

        async def replay_receive() -> Message:
            nonlocal body_replayed
            if not body_replayed:
                body_replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        texts = self._parse_user_texts(body)
        if texts:
            try:
                for text in texts:
                    verdict = await guardrails.check_input(text)
                    if not verdict.allowed:
                        await self._send_blocked(scope, send, guardrails.settings.blocked_message)
                        return
            except Exception:
                logger.exception("Guardrails check failed with fail-open disabled.")
                await self._send_unavailable(scope, send)
                return

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _read_body(receive: Receive) -> bytes:
        chunks: list[bytes] = []
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        return b"".join(chunks)

    @staticmethod
    def _parse_user_texts(body: bytes) -> list[str]:
        if not body:
            return []
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return []
        return extract_user_texts(payload)

    @staticmethod
    def _request_id(scope: Scope) -> str | None:
        return (scope.get("state") or {}).get("request_id")

    @classmethod
    async def _send_json(cls, scope: Scope, send: Send, status: int, error: str, message: str) -> None:
        request_id = cls._request_id(scope)
        content: dict = {"error": error, "message": message}
        if request_id:
            content["request_id"] = request_id
        body = json.dumps(content, ensure_ascii=False).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("latin-1")),
        ]
        if request_id:
            headers.append((b"x-request-id", request_id.encode("latin-1")))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    @classmethod
    async def _send_blocked(cls, scope: Scope, send: Send, message: str) -> None:
        record_guardrails_block("input")
        path = scope.get("path", "")
        logger.warning(
            "Request blocked by the guardrails input filter.",
            extra={"path": path, "request_id": cls._request_id(scope)},
        )
        if path.endswith("/stream"):
            await cls._send_blocked_sse(scope, send, message)
            return
        await cls._send_json(scope, send, 400, "input_blocked_by_guardrails", message)

    @classmethod
    async def _send_blocked_sse(cls, scope: Scope, send: Send, message: str) -> None:
        request_id = cls._request_id(scope)
        progress = {
            "type": "progress",
            "step": "guardrails",
            "message": "Estamos revisando tu consulta…",
        }
        error: dict = {
            "type": "error",
            "message": message,
            "code": "input_blocked_by_guardrails",
        }
        if request_id:
            error["request_id"] = request_id

        def _frame(payload: dict) -> bytes:
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

        headers = [
            (b"content-type", b"text/event-stream; charset=utf-8"),
            (b"cache-control", b"no-cache"),
            (b"connection", b"keep-alive"),
            (b"x-accel-buffering", b"no"),
        ]
        if request_id:
            headers.append((b"x-request-id", request_id.encode("latin-1")))

        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": _frame(progress), "more_body": True})
        await send({"type": "http.response.body", "body": _frame(error), "more_body": False})

    @classmethod
    async def _send_unavailable(cls, scope: Scope, send: Send) -> None:
        await cls._send_json(
            scope,
            send,
            503,
            "guardrails_unavailable",
            "El filtro de seguridad no está disponible.",
        )


def add_guardrails_middleware(app: FastAPI) -> None:
    app.add_middleware(GuardrailsMiddleware)
