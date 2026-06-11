"""Context-local request id, set by the logging middleware and read by the
shared HTTP client so the X-Request-ID header propagates to downstream services."""

from contextvars import ContextVar
from typing import Optional

_request_id: ContextVar[Optional[str]] = ContextVar("_request_id", default=None)


def set_request_id(request_id: Optional[str]) -> None:
    _request_id.set(request_id)


def get_request_id() -> Optional[str]:
    return _request_id.get()
