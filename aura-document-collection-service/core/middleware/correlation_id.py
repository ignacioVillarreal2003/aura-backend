import logging
import threading
import uuid

_correlation_id = threading.local()

HEADER_NAME = "X-Correlation-Id"


def get_correlation_id() -> str:
    return getattr(_correlation_id, "value", "-")


def set_correlation_id(value: str):
    _correlation_id.value = value


class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = get_correlation_id()
        return True


class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cid = request.headers.get(HEADER_NAME) or str(uuid.uuid4())
        set_correlation_id(cid)
        request.correlation_id = cid

        response = self.get_response(request)
        response[HEADER_NAME] = cid
        return response
