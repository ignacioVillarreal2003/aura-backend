"""Project-wide DRF exception handler.

* Consistent error envelope: every error response carries a ``request_id`` (and
  a ``detail`` when the body is not already a structured error).
* No leaked internals: an unhandled exception becomes a generic 500 while the
  full traceback is logged (tagged with the request id) for debugging — instead
  of returning a stack trace (Django's debug 500 page) to the caller.
"""
import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from accounts.middleware.request_id_middleware import get_request_id

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    request_id = get_request_id()

    if response is not None:
        # Handled DRF exception (validation, auth, throttling, ...). Preserve
        # the existing structure (e.g. field-level errors) and just tag it so
        # the client can quote the id when reporting a problem.
        if isinstance(response.data, dict):
            response.data.setdefault('request_id', request_id)
        else:
            response.data = {'detail': response.data, 'request_id': request_id}
        return response

    # Not a DRF exception -> would have been an unhandled 500. Log the full
    # traceback (correlated by request id) and return a generic envelope.
    logger.exception('Unhandled exception while processing request', extra={'request_id': request_id})
    return Response(
        {'detail': 'Internal server error.', 'request_id': request_id},
        status=500,
    )
