"""Server-Sent Events (text/event-stream) helpers.

SSE wire format (RFC 8895):
  event: <type>\n
  data: <json-payload>\n
  \n
Each frame must end with a blank line to signal the boundary.
"""

import json
from typing import Any


def format_sse(event: str, data: Any) -> str:
    """Return a single, correctly encoded SSE frame."""
    payload = json.dumps(data, default=str, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


# ---------------------------------------------------------------------------
# Canonical event constructors – centralise field names so consumers and
# producers never drift apart.
# ---------------------------------------------------------------------------

def sse_start(chat_id: int) -> str:
    return format_sse("start", {"chat_id": chat_id, "status": "processing"})


def sse_delta(delta: str) -> str:
    return format_sse("delta", {"delta": delta})


def sse_complete(message_id: int, chat_id: int) -> str:
    return format_sse("complete", {
        "message_id": message_id,
        "chat_id": chat_id,
        "finish_reason": "stop",
    })


def sse_error(code: str, message: str) -> str:
    return format_sse("error", {"code": code, "message": message})
