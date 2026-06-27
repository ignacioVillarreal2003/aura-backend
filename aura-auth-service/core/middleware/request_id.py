"""ID de correlacion por peticion para poder seguirla en los logs."""
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
    """Asigna un id a cada peticion y lo devuelve en la respuesta."""

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
    """Agrega el request id a cada registro de log."""

    def filter(self, record):
        record.request_id = get_request_id() or "-"
        return True
