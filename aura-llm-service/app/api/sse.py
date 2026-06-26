import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from pydantic import BaseModel
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

_HEARTBEAT_FRAME = b": ping\n\n"
_HEARTBEAT_INTERVAL_SECONDS = 15.0

_FALLBACK_ERROR_PAYLOAD = {
    "type": "error",
    "message": "El servicio no pudo completar la respuesta.",
    "code": "internal_error",
}
_FALLBACK_ERROR_FRAME = f"data: {json.dumps(_FALLBACK_ERROR_PAYLOAD, ensure_ascii=False)}\n\n".encode("utf-8")


def format_sse_event(event: BaseModel) -> bytes:
    return f"data: {event.model_dump_json()}\n\n".encode("utf-8")


def sse_response(events: AsyncIterator[BaseModel]) -> StreamingResponse:
    async def _stream() -> AsyncIterator[bytes]:
        iterator = events.__aiter__()
        pending: asyncio.Task | None = None
        try:
            while True:
                if pending is None:
                    pending = asyncio.ensure_future(anext(iterator))
                done, _ = await asyncio.wait(
                    {pending}, timeout=_HEARTBEAT_INTERVAL_SECONDS
                )
                if not done:
                    yield _HEARTBEAT_FRAME
                    continue
                task, pending = pending, None
                try:
                    event = task.result()
                except StopAsyncIteration:
                    return
                except Exception:
                    logger.exception("SSE event source failed; emitting terminal error event.")
                    yield _FALLBACK_ERROR_FRAME
                    return
                try:
                    frame = format_sse_event(event)
                except Exception:
                    logger.exception("SSE event serialization failed; emitting terminal error event.")
                    yield _FALLBACK_ERROR_FRAME
                    return
                yield frame
        finally:
            if pending is not None:
                pending.cancel()
                with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
                    await pending

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
