"""Unit tests for sse_response: normal framing, clean completion, and the
defensive terminal error frame emitted when the event source raises or an event
fails to serialize (so the client never sees a silently truncated stream)."""
from collections.abc import AsyncIterator

from pydantic import BaseModel

from app.api.sse import _FALLBACK_ERROR_FRAME, format_sse_event, sse_response


class _Event(BaseModel):
    type: str
    text: str


async def _collect(response) -> list[bytes]:
    return [chunk async for chunk in response.body_iterator]


async def test_normal_events_are_framed_as_sse():
    async def gen() -> AsyncIterator[BaseModel]:
        yield _Event(type="delta", text="a")
        yield _Event(type="complete", text="done")

    frames = await _collect(sse_response(gen()))

    assert frames == [
        format_sse_event(_Event(type="delta", text="a")),
        format_sse_event(_Event(type="complete", text="done")),
    ]


async def test_empty_stream_completes_cleanly():
    async def gen() -> AsyncIterator[BaseModel]:
        return
        yield  # pragma: no cover - makes this an async generator

    frames = await _collect(sse_response(gen()))

    assert frames == []


async def test_source_raising_emits_terminal_error_frame():
    async def gen() -> AsyncIterator[BaseModel]:
        yield _Event(type="delta", text="a")
        raise RuntimeError("boom")

    frames = await _collect(sse_response(gen()))

    assert frames[0] == format_sse_event(_Event(type="delta", text="a"))
    assert frames[-1] == _FALLBACK_ERROR_FRAME


async def test_serialization_failure_emits_terminal_error_frame():
    class _Unserializable:
        def model_dump_json(self) -> str:
            raise ValueError("cannot serialize")

    async def gen() -> AsyncIterator[BaseModel]:
        yield _Unserializable()  # type: ignore[misc]

    frames = await _collect(sse_response(gen()))

    assert frames == [_FALLBACK_ERROR_FRAME]


async def test_error_frame_carries_typed_error_shape():
    import json

    payload = json.loads(_FALLBACK_ERROR_FRAME.decode("utf-8").removeprefix("data: ").strip())
    assert payload["type"] == "error"
    assert payload["code"] == "internal_error"
    assert payload["message"]
