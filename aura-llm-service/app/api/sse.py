"""Server-Sent Events helpers shared by the streaming controllers."""

from collections.abc import AsyncIterator

from pydantic import BaseModel
from starlette.responses import StreamingResponse

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # Tell nginx not to buffer the stream so events reach the client as emitted.
    "X-Accel-Buffering": "no",
}


def format_sse_event(event: BaseModel) -> bytes:
    return f"data: {event.model_dump_json()}\n\n".encode("utf-8")


def sse_response(events: AsyncIterator[BaseModel]) -> StreamingResponse:
    async def _stream() -> AsyncIterator[bytes]:
        async for event in events:
            yield format_sse_event(event)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
