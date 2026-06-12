import asyncio
import contextlib
from collections.abc import AsyncIterator
from pydantic import BaseModel
from starlette.responses import StreamingResponse

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

_HEARTBEAT_FRAME = b": ping\n\n"
_HEARTBEAT_INTERVAL_SECONDS = 15.0


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
                yield format_sse_event(event)
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
