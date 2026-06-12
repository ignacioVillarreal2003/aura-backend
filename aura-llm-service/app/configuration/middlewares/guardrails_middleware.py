import json
import logging
from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

_EXCLUDED_PATH_PREFIXES = (
    "/api/v1/health",
    "/api/v1/ready",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/metrics",
)

# JSON fields that carry free-form user intent. Bulk document content
# (processing endpoints) is deliberately not inspected: it is data to process,
# not instructions from the end user, and the per-flow prompts already treat
# it as untrusted input.
_USER_TEXT_FIELDS = ("instruction", "question")


def extract_user_texts(payload: object) -> list[str]:
    """Pull the user-authored texts out of a request body."""
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
    """Runs the NeMo Guardrails input filter on every JSON POST under /api/v1.

    Sits innermost in the middleware chain, so authentication and body size
    limits have already been enforced. The body is buffered and replayed to
    the downstream app.
    """

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

        async def replay_receive() -> Message:
            return {"type": "http.request", "body": body, "more_body": False}

        texts = self._parse_user_texts(body)
        if texts:
            try:
                for text in texts:
                    verdict = await guardrails.check_input(text)
                    if not verdict.allowed:
                        await self._send_blocked(scope, send, guardrails.settings.blocked_message)
                        return
            except Exception:
                # Only reachable with fail_open disabled: reject explicitly.
                logger.exception("Guardrails check failed with fail-open disabled.")
                await self._send_unavailable(send)
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
    async def _send_blocked(scope: Scope, send: Send, message: str) -> None:
        logger.warning(
            "Request blocked by the guardrails input filter.",
            extra={"path": scope.get("path")},
        )
        body = json.dumps(
            {"detail": message, "error": "input_blocked_by_guardrails"},
            ensure_ascii=False,
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    async def _send_unavailable(send: Send) -> None:
        body = json.dumps(
            {
                "detail": "El filtro de seguridad no está disponible.",
                "error": "guardrails_unavailable",
            },
            ensure_ascii=False,
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 503,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def add_guardrails_middleware(app: FastAPI) -> None:
    app.add_middleware(GuardrailsMiddleware)
