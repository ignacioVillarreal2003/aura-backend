import logging
import re
import uuid
from contextvars import ContextVar

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")
_CID_RE = re.compile(r"^[a-zA-Z0-9\-]{1,64}$")

HEADER_NAME = "X-Correlation-Id"


def get_correlation_id() -> str:
    return _correlation_id.get()


def set_correlation_id(value: str) -> None:
    _correlation_id.set(value)


class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = get_correlation_id()
        return True


class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raw = request.headers.get(HEADER_NAME)
        cid = raw if raw and _CID_RE.match(raw) else str(uuid.uuid4())
        set_correlation_id(cid)
        request.correlation_id = cid

        response = self.get_response(request)
        response[HEADER_NAME] = cid
        return response
