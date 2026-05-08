import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from core.exceptions.base import ServiceException

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    if isinstance(exc, ServiceException):
        logger.warning(
            "Service exception: %s",
            exc.detail,
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "view": context.get("view").__class__.__name__ if context.get("view") else None,
            },
        )
        return Response(
            {
                "error": exc.error_code,
                "detail": exc.detail,
                "status_code": exc.status_code,
            },
            status=exc.status_code,
        )

    response = exception_handler(exc, context)

    if response is not None:
        response.data = {
            "error": _status_to_error_code(response.status_code),
            "detail": response.data,
            "status_code": response.status_code,
        }
        return response

    logger.exception(
        "Unhandled exception in view %s",
        context.get("view").__class__.__name__ if context.get("view") else "unknown",
    )
    return Response(
        {
            "error": "internal_error",
            "detail": "An unexpected error occurred",
            "status_code": 500,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _status_to_error_code(status_code: int) -> str:
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        429: "throttled",
        503: "service_unavailable",
    }
    return mapping.get(status_code, "error")
