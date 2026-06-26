"""Per-request correlation ID.

Generates (or accepts, via the inbound ``X-Request-ID`` header) a short id,
exposes it through a ContextVar so any log record can be tagged with it, and
echoes it back on the response ``X-Request-ID`` header. This lets a single
request be traced across log lines — and, when the gateway forwards the
header, across services.
"""
from __future__ import annotations

import contextvars
import logging
import uuid
from typing import Optional

_REQUEST_ID_HEADER = "X-Request-ID"

_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "aura_request_id", default=None
)


def get_request_id() -> Optional[str]:
    return _request_id.get()


class RequestIDMiddleware:
    """Assigns a request id (inbound header or a fresh uuid) for the duration
    of the request and echoes it on the response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get(_REQUEST_ID_HEADER, "").strip()
        request_id = incoming or uuid.uuid4().hex
        request.request_id = request_id
        token = _request_id.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            try:
                _request_id.reset(token)
            except (ValueError, LookupError):
                _request_id.set(None)
        response.headers[_REQUEST_ID_HEADER] = request_id
        return response


class RequestIDLogFilter(logging.Filter):
    """Inject the current request id into every log record so the JSON
    formatter can emit it. Records outside a request context get ``-``."""

    def filter(self, record):
        record.request_id = get_request_id() or "-"
        return True
