import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from core.exceptions.base import ServiceException
from core.middleware.correlation_id import get_correlation_id

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
                "correlation_id": get_correlation_id(),
            },
            status=exc.status_code,
        )

    response = exception_handler(exc, context)

    if response is not None:
        error_detail = response.data
        error_code = _status_to_error_code(response.status_code)
        cid = get_correlation_id()

        if isinstance(error_detail, dict) and "detail" in error_detail:
            response.data = {
                "error": error_code,
                "detail": str(error_detail["detail"]),
                "status_code": response.status_code,
                "correlation_id": cid,
            }
        elif isinstance(error_detail, dict):
            response.data = {
                "error": error_code,
                "detail": "Validation failed",
                "fields": _serialize_validation_errors(error_detail),
                "status_code": response.status_code,
                "correlation_id": cid,
            }
        elif isinstance(error_detail, list):
            first = str(error_detail[0]) if error_detail else "Validation error"
            response.data = {
                "error": error_code,
                "detail": first,
                "status_code": response.status_code,
                "correlation_id": cid,
            }
        else:
            response.data = {
                "error": error_code,
                "detail": str(error_detail),
                "status_code": response.status_code,
                "correlation_id": cid,
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
            "correlation_id": get_correlation_id(),
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _serialize_validation_errors(data) -> dict | list | str:
    if isinstance(data, dict):
        return {k: _serialize_validation_errors(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_serialize_validation_errors(item) for item in data]
    return str(data)


def _status_to_error_code(status_code: int) -> str:
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        413: "payload_too_large",
        429: "throttled",
        500: "internal_error",
        502: "bad_gateway",
        503: "service_unavailable",
    }
    return mapping.get(status_code, "error")
