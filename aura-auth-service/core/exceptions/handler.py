"""Manejador de errores de DRF: agrega request_id y oculta los 500 internos."""
import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from core.middleware.request_id import get_request_id

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    request_id = get_request_id()

    if response is not None:
        if isinstance(response.data, dict):
            response.data.setdefault('request_id', request_id)
        else:
            response.data = {'detail': response.data, 'request_id': request_id}
        return response

    logger.exception('Unhandled exception while processing request', extra={'request_id': request_id})
    return Response(
        {'detail': 'Internal server error.', 'request_id': request_id},
        status=500,
    )
